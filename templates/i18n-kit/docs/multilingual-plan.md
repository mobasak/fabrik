# Multilingual SaaS Bible

**Last Updated:** 2026-05-19
**Applies to:** Any web SaaS project (Flask, FastAPI, Next.js, etc.)
**Battle-tested on:** Tojlo (738 keys, 6 languages, 24 pages). Reusable across all projects.

---

## Contents

- [Principles](#principles)
- [Target Languages](#target-languages)
- [Architecture Decision](#architecture-decision)
- [File Structure](#file-structure)
- [JSON Format Specification](#json-format-specification)
- [Key Naming Convention](#key-naming-convention)
- [Pluralization and ICU MessageFormat](#pluralization-and-icu-messageformat)
- [The i18n Loader (i18n.js)](#the-i18n-loader)
- [Template Integration](#template-integration)
- [Language Switcher](#language-switcher)
- [User Preference Persistence](#user-preference-persistence)
- [Date, Time, Number, and Currency Formatting](#date-time-number-and-currency-formatting)
- [Text Expansion and Layout](#text-expansion-and-layout)
- [Character Encoding](#character-encoding)
- [RTL Support](#rtl-support)
- [Translation Workflow](#translation-workflow)
- [Quality Validation](#quality-validation)
- [String Inventory Template](#string-inventory-template)
- [What NOT to Translate](#what-not-to-translate)
- [Rollout Plan](#rollout-plan)
- [Checklist](#checklist)
- [Anti-Patterns](#anti-patterns-production-killers)
- [Email and Notification Localization](#email-and-notification-localization)
- [SEO and URL Strategy](#seo-and-url-strategy)
- [Testing Strategy](#testing-strategy)
- [Production Gotchas](#production-gotchas-learned-from-industry)
- [References](#references)

---

## Principles

1. **English is the source of truth.** `en.json` is always complete. All other files are translations of it.
2. **Fallback to English.** If a key is missing in the target language, show the English value. Never show a raw key or blank.
3. **Strings live in JSON, not in code.** No hardcoded user-facing text in templates or JS. Every visible string has a key.
4. **Translators never touch code.** They receive a JSON file, translate the values, return it. No HTML, no JS, no Jinja.
5. **Ship in English first.** i18n system works from day one with one language. Adding a language = adding a JSON file.
6. **Locale-aware formatting.** Dates, numbers, currency use `Intl` API — never hardcode format patterns.
7. **Test at the longest language.** Portuguese/Spanish expand 20-30%. If the UI works in Portuguese, it works everywhere.
8. **No machine translation without review.** AI does the first pass. A native speaker reviews before shipping.

---

## Target Languages

| Tier | Language | Code | Active users | Purchasing power | English proficiency | Priority |
|------|----------|------|--------------|-----------------|-------------------|----------|
| 0 | English | `en` | Default | — | — | Shipped |
| 1 | Spanish | `es` | 86M+ (Mexico+LatAm+Spain) | Medium | Low-Medium | High |
| 1 | Portuguese (Brazil) | `pt-BR` | 150M | Medium | Low | High |
| 2 | Japanese | `ja` | 79M | Very High | Low | High (revenue) |
| 3 | Bahasa Indonesia | `id` | 151M | Low-Medium | Low | Medium (volume) |
| 3 | Turkish | `tr` | 58M | Medium | Medium | Medium (home market) |

**Ship order:** `en` → `tr` (home market, test the system) → `es` + `pt-BR` → `ja` → `id`

---

## Architecture Decision

### Client-side JSON + JS loader (chosen)

```
Browser loads page → HTML has English text (default) → i18n.js loads
→ reads language preference (cookie → browser → default)
→ fetches /{lang}.json → replaces DOM text via data-i18n attributes
```

**Why this over Flask-Babel/gettext:**

| Factor | gettext (.po/.mo) | JSON + JS (chosen) |
|--------|-------------------|-------------------|
| Compilation step | Yes (pybabel compile) | No |
| Server restart on translation change | Yes | No |
| Works with JS-rendered content | No (server-only) | Yes |
| Translator edits | .po files (special format) | JSON (universal) |
| Framework-locked | Flask-specific | Any framework |
| CDN-cacheable | No | Yes |
| SEO (initial HTML) | Translated server-side | English (acceptable for SaaS dashboard — not public marketing) |

**When to use gettext instead:** Public-facing marketing pages where SEO in target language matters. For authenticated SaaS dashboards, client-side JSON is the right call.

---

## File Structure

```
dashboard/
├── static/
│   ├── js/
│   │   └── i18n.js              # The loader (one file, all projects)
│   └── i18n/
│       ├── en.json              # English — source of truth
│       ├── tr.json              # Turkish
│       ├── es.json              # Spanish
│       ├── pt-BR.json           # Portuguese (Brazil)
│       ├── ja.json              # Japanese
│       └── id.json              # Bahasa Indonesia
└── templates/
    └── base.html                # loads i18n.js, has language switcher
```

---

## JSON Format Specification

### Structure: nested, 2-3 levels max

```json
{
  "_meta": {
    "language": "en",
    "name": "English",
    "nativeName": "English",
    "rtl": false,
    "version": "1.0.0",
    "lastUpdated": "2026-05-18",
    "completeness": 1.0
  },
  "nav": {
    "batch": "Batch",
    "queue": "Queue"
  },
  "queue": {
    "title": "Job Queue",
    "confirm_retry": "Retry this failed job? No additional credits charged.",
    "jobs_count": "{count, plural, =0 {No jobs} one {1 job} other {{count} jobs}}"
  }
}
```

### Rules

1. **`_meta` block required** in every file. `completeness` = ratio of translated keys to total English keys (0.0-1.0).
2. **Nesting max 3 levels:** `section.subsection.key`. Never `section.subsection.group.subgroup.key`.
3. **Values are strings only.** No arrays, no nested objects inside leaf values.
4. **ICU MessageFormat** for plurals, gender, select. See section below.
5. **Variables use `{name}` syntax.** Single curly braces. `"Upload {filename} ({size} MB)?"`
6. **No HTML in values.** If a string needs markup, split it into parts or use variable interpolation.
7. **Keys are English-descriptive.** `queue.confirm_retry` not `queue.str_47` or `queue.retry_confirmation_dialog_message`.

---

## Key Naming Convention

### Pattern: `{page}.{element}_{action}`

| Pattern | Example | When to use |
|---------|---------|-------------|
| `{page}.{noun}` | `nav.queue`, `auth.email` | Static labels |
| `{page}.{noun}_{action}` | `queue.confirm_retry` | Action-related strings |
| `{page}.{noun}_{state}` | `queue.no_jobs` | State descriptions |
| `common.{noun}` | `common.save`, `common.cancel` | Shared across 3+ pages |
| `error.{type}` | `error.not_found` | Error messages |

### Namespace allocation

| Namespace | Scope |
|-----------|-------|
| `nav` | Navigation bar labels |
| `auth` | Login, register, forgot/reset password, email verified |
| `queue` | Job queue page |
| `watchlists` | Watchlist management |
| `library` | Library browsing |
| `batch` | Batch processing |
| `settings` | User settings |
| `pricing` | Pricing and payments |
| `admin` | Admin panel (optional — may stay English) |
| `common` | Shared: save, cancel, delete, loading, credits, errors |
| `failure` | Job failure reason labels |
| `error` | Error pages |

### Anti-patterns

| Bad | Why | Good |
|-----|-----|------|
| `str_1`, `str_2` | No meaning | `auth.sign_in` |
| `Submit` (English as key) | Can't have two different "Submit" | `auth.sign_in`, `batch.submit` |
| `queue.retryConfirmationDialogMessageText` | Too long | `queue.confirm_retry` |
| `queue.buttons.retry.confirm.text` | Too nested | `queue.confirm_retry` |

---

## Pluralization and ICU MessageFormat

For strings that change based on count, gender, or selection, use ICU MessageFormat syntax in JSON values.

### Plurals

```json
{
  "queue.jobs_count": "{count, plural, =0 {No jobs} one {1 job} other {{count} jobs}}",
  "watchlists.videos_discovered": "{count, plural, =0 {No videos} one {1 video discovered} other {{count} videos discovered}}"
}
```

**Why not separate keys (`jobs_zero`, `jobs_one`, `jobs_other`):** ICU keeps the plural logic in one string — translators see the full context. Languages like Arabic have 6 plural forms; Russian has 4. ICU handles all of them in one entry.

### Select (gender, role, etc.)

```json
{
  "team.role_label": "{role, select, admin {Administrator} member {Member} viewer {Viewer} other {Unknown}}"
}
```

### JS implementation

Use the `Intl.PluralRules` API + a lightweight ICU parser, or the `intl-messageformat` library (~3KB gzipped):

```javascript
import IntlMessageFormat from 'intl-messageformat';

function formatICU(pattern, values, locale) {
    try {
        return new IntlMessageFormat(pattern, locale).format(values);
    } catch {
        return pattern; // fallback: show raw pattern
    }
}

// Usage
formatICU(I18N.t('queue.jobs_count'), { count: 42 }, 'en');
// → "42 jobs"
```

If avoiding dependencies, handle simple `{count}` interpolation inline and skip full ICU for v1. Add `intl-messageformat` when pluralization matters (Phase 2+).

---

## The i18n Loader

`dashboard/static/js/i18n.js` — one file, copy to any project:

```javascript
const I18N = {
    _strings: {},
    _lang: 'en',
    _fallback: {},
    _supported: ['en', 'tr', 'es', 'pt-br', 'ja', 'id'],

    async init() {
        this._lang = this._detectLanguage();

        // Always load English as fallback
        this._fallback = await this._load('en');

        if (this._lang !== 'en') {
            this._strings = await this._load(this._lang);
        } else {
            this._strings = this._fallback;
        }

        this._applyToDOM();
        document.documentElement.lang = this._lang;

        // Show current language in switcher
        const el = document.getElementById('currentLangLabel');
        if (el) el.textContent = this._strings?._meta?.nativeName || 'English';
    },

    _detectLanguage() {
        // Priority: cookie → URL param → browser → default
        const cookie = document.cookie.split(';')
            .find(c => c.trim().startsWith('lang='));
        if (cookie) {
            const val = cookie.split('=')[1].trim().toLowerCase();
            if (this._supported.includes(val)) return val;
        }

        const urlParam = new URLSearchParams(location.search).get('lang');
        if (urlParam && this._supported.includes(urlParam.toLowerCase())) {
            return urlParam.toLowerCase();
        }

        const browserLang = navigator.language.toLowerCase();
        const match = this._supported.find(l => browserLang.startsWith(l));
        if (match) return match;

        return 'en';
    },

    async _load(lang) {
        try {
            const resp = await fetch(`/static/i18n/${lang}.json`);
            if (!resp.ok) return {};
            return await resp.json();
        } catch { return {}; }
    },

    // Get translation by dot-path: t('nav.queue') → "Queue"
    t(key, vars = {}) {
        let val = this._resolve(this._strings, key);
        if (val === undefined) val = this._resolve(this._fallback, key);
        if (val === undefined) return key;

        // Variable interpolation: {name} → value
        if (typeof val === 'string' && Object.keys(vars).length) {
            for (const [k, v] of Object.entries(vars)) {
                val = val.replaceAll(`{${k}}`, v);
            }
        }
        return val;
    },

    _resolve(obj, path) {
        return path.split('.').reduce((o, k) => o?.[k], obj);
    },

    // Apply to all elements with data-i18n, data-i18n-placeholder, data-i18n-title
    _applyToDOM() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const val = this.t(key);
            if (val !== key) el.textContent = val;
        });

        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            const val = this.t(key);
            if (val !== key) el.placeholder = val;
        });

        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            const val = this.t(key);
            if (val !== key) el.title = val;
        });

        document.querySelectorAll('[data-i18n-html]').forEach(el => {
            const key = el.getAttribute('data-i18n-html');
            const val = this.t(key);
            if (val !== key) el.innerHTML = val;
        });
    },

    setLanguage(lang) {
        if (!this._supported.includes(lang)) return;
        document.cookie = `lang=${lang};path=/;max-age=${365*86400};SameSite=Lax`;
        location.reload();
    },

    // Get current language
    get lang() { return this._lang; },

    // Format date in current locale
    formatDate(date, style = 'medium') {
        return new Intl.DateTimeFormat(this._lang, { dateStyle: style }).format(new Date(date));
    },

    // Format date+time in current locale
    formatDateTime(date, dateStyle = 'medium', timeStyle = 'short') {
        return new Intl.DateTimeFormat(this._lang, { dateStyle, timeStyle }).format(new Date(date));
    },

    // Format number in current locale
    formatNumber(num) {
        return new Intl.NumberFormat(this._lang).format(num);
    },

    // Format currency
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat(this._lang, { style: 'currency', currency }).format(amount);
    },

    // Format relative time ("3 minutes ago", "in 2 hours")
    formatRelative(date) {
        const seconds = Math.round((new Date(date) - new Date()) / 1000);
        const units = [
            { unit: 'year', sec: 31536000 },
            { unit: 'month', sec: 2592000 },
            { unit: 'week', sec: 604800 },
            { unit: 'day', sec: 86400 },
            { unit: 'hour', sec: 3600 },
            { unit: 'minute', sec: 60 },
            { unit: 'second', sec: 1 },
        ];
        for (const { unit, sec } of units) {
            if (Math.abs(seconds) >= sec) {
                return new Intl.RelativeTimeFormat(this._lang, { numeric: 'auto' })
                    .format(Math.round(seconds / sec), unit);
            }
        }
        return new Intl.RelativeTimeFormat(this._lang, { numeric: 'auto' }).format(0, 'second');
    }
};

document.addEventListener('DOMContentLoaded', () => I18N.init());
```

---

## Template Integration

### HTML: add `data-i18n` attributes

**Before (hardcoded):**
```html
<a class="nav-link" href="/queue">Queue</a>
<button class="btn btn-primary">Sign In</button>
<input placeholder="you@example.com">
<button title="Retry this job">
```

**After (i18n-ready):**
```html
<a class="nav-link" href="/queue" data-i18n="nav.queue">Queue</a>
<button class="btn btn-primary" data-i18n="auth.sign_in">Sign In</button>
<input data-i18n-placeholder="auth.email_placeholder" placeholder="you@example.com">
<button data-i18n-title="queue.retry_title" title="Retry this job">
```

English text remains as the default — visible before JS loads, works without JS, good for SEO crawlers.

### JavaScript: use `I18N.t()`

**Before:**
```javascript
if (!confirm('Retry this failed job?')) return;
toast.textContent = `Uploaded ${data.video_id}. Job retriggered.`;
```

**After:**
```javascript
if (!confirm(I18N.t('queue.confirm_retry'))) return;
toast.textContent = I18N.t('queue.upload_success', { video_id: data.video_id });
```

### Load i18n.js in base.html

```html
<script src="/static/js/i18n.js"></script>
```

Place before `</body>` but before any page-specific JS that uses `I18N.t()`.

---

## Language Switcher

Add to navbar (base.html), next to user dropdown:

```html
<div class="dropdown">
    <button class="btn btn-outline-secondary btn-sm dropdown-toggle" data-bs-toggle="dropdown">
        <i class="bi bi-globe2 me-1"></i>
        <span id="currentLangLabel">English</span>
    </button>
    <ul class="dropdown-menu dropdown-menu-end">
        <li><a class="dropdown-item" href="#" onclick="I18N.setLanguage('en')">English</a></li>
        <li><a class="dropdown-item" href="#" onclick="I18N.setLanguage('tr')">Turkce</a></li>
        <li><a class="dropdown-item" href="#" onclick="I18N.setLanguage('es')">Espanol</a></li>
        <li><a class="dropdown-item" href="#" onclick="I18N.setLanguage('pt-br')">Portugues (BR)</a></li>
        <li><a class="dropdown-item" href="#" onclick="I18N.setLanguage('ja')">日本語</a></li>
        <li><a class="dropdown-item" href="#" onclick="I18N.setLanguage('id')">Bahasa Indonesia</a></li>
    </ul>
</div>
```

For standalone auth pages (no base.html), add a minimal switcher in the footer:

```html
<div class="text-center mt-2">
    <small class="text-secondary">
        <a href="#" onclick="I18N.setLanguage('en')">EN</a> |
        <a href="#" onclick="I18N.setLanguage('tr')">TR</a> |
        <a href="#" onclick="I18N.setLanguage('es')">ES</a> |
        <a href="#" onclick="I18N.setLanguage('pt-br')">PT</a> |
        <a href="#" onclick="I18N.setLanguage('ja')">JA</a> |
        <a href="#" onclick="I18N.setLanguage('id')">ID</a>
    </small>
</div>
```

---

## User Preference Persistence

### Detection priority

1. **Cookie** `lang=tr` (set by switcher or server)
2. **URL parameter** `?lang=tr` (for sharing a link in a specific language)
3. **Browser** `navigator.language` (auto-detect on first visit)
4. **Default** `en`

### Server-side (optional, for logged-in users)

Store in the `users.settings` JSONB column:

```python
@app.route('/api/user/language', methods=['POST'])
@login_required
def set_language():
    lang = request.json.get('lang', 'en')
    supported = ('en', 'tr', 'es', 'pt-br', 'ja', 'id')
    if lang not in supported:
        return jsonify({'error': 'Unsupported language'}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET settings = jsonb_set(COALESCE(settings,'{}'), '{language}', %s)
        WHERE id = %s
    """, (f'"{lang}"', current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'language': lang})
```

On login, set the cookie from the stored preference:

```html
{% if current_user.is_authenticated %}
<script>
    const savedLang = {{ current_user.settings | tojson }};
    if (savedLang?.language) {
        document.cookie = `lang=${savedLang.language};path=/;max-age=${365*86400};SameSite=Lax`;
    }
</script>
{% endif %}
```

---

## Date, Time, Number, and Currency Formatting

**Never hardcode format patterns.** Always use `Intl` APIs.

| Data type | API | Example (en) | Example (ja) | Example (tr) |
|-----------|-----|-------------|-------------|-------------|
| Date | `Intl.DateTimeFormat` | May 18, 2026 | 2026年5月18日 | 18 Mayis 2026 |
| Time | `Intl.DateTimeFormat` | 3:45 PM | 15:45 | 15:45 |
| Number | `Intl.NumberFormat` | 1,234.56 | 1,234.56 | 1.234,56 |
| Currency | `Intl.NumberFormat` | $12.50 | $12.50 | 12,50 $ |
| Relative | `Intl.RelativeTimeFormat` | 3 minutes ago | 3 分前 | 3 dakika once |

The `I18N` loader includes `formatDate()`, `formatDateTime()`, `formatNumber()`, `formatCurrency()`, and `formatRelative()` methods that use the current language automatically.

### Storage rule

- Store all timestamps in **UTC** in the DB
- Convert to user's timezone **at display time only**
- Store numbers as numbers, not formatted strings
- Store currency amounts as integers (cents) or decimals — format at display time

---

## Text Expansion and Layout

| Language | Expansion vs English | Impact |
|----------|---------------------|--------|
| Spanish | +20-30% | Buttons, nav labels may wrap |
| Portuguese | +20-30% | Same as Spanish |
| Japanese | -10-20% (fewer chars, wider glyphs) | May need wider chars |
| Turkish | +10-15% | Minor |
| Indonesian | +10-20% | Minor |

### Mitigation rules

1. **Buttons:** use `min-width`, not `width`. Or let them grow with content.
2. **Nav labels:** allow wrapping or use shorter translations.
3. **Table headers:** `white-space: nowrap` is OK if table has `table-responsive`.
4. **Modals/cards:** use `min-height`, not `height`.
5. **Test at Portuguese:** if it fits in pt-BR, it fits everywhere.

### Pseudo-localization (development tool)

Before real translations are ready, test layout with pseudo-locale that expands strings ~30%:

```javascript
// In dev mode only
function pseudoLocalize(str) {
    const map = { a:'a', e:'e', i:'i', o:'o', u:'u' };
    return '[' + str.replace(/[aeiou]/gi, c => (map[c.toLowerCase()] || c) + '\u0301') + ' +++]';
}
```

This makes every string ~30% longer and visually distinct, exposing layout breakage without needing real translations.

---

## Character Encoding

### Requirements (already met in this project)

- `<meta charset="UTF-8">` in every template
- PostgreSQL stores text as UTF-8
- Python reads B2 files with `.content.decode('utf-8')`
- JSON files saved as UTF-8 without BOM

### Characters that must render correctly

| Language | Critical characters |
|----------|-------------------|
| Turkish | `c, s, g, i, o, u, I, S, G` (dotless i: `i` ≠ `i`) |
| Japanese | Kanji, Hiragana, Katakana, full-width punctuation |
| Portuguese | `a, o, c, e, e, a, u` |
| Spanish | `n, a, e, i, o, u, u, ?, !` |
| Indonesian | Standard Latin (no special chars) |

### Turkish `i` problem

Turkish has two versions of `i`: dotted (`i`/`I`) and dotless (`i`/`I`). JavaScript's `.toLowerCase()` and `.toUpperCase()` handle this wrong in the default locale. If doing string comparison for Turkish text:

```javascript
str.toLocaleLowerCase('tr'); // not .toLowerCase()
```

---

## RTL Support

None of the current target languages are RTL. If Arabic or Hebrew is added later:

1. Add `"rtl": true` in the language's `_meta` block
2. Loader sets `document.dir = 'rtl'` and `document.documentElement.dir = 'rtl'`
3. CSS: use logical properties (`margin-inline-start` instead of `margin-left`)
4. Bootstrap 5.3 has built-in RTL support via `<html dir="rtl">`

---

## Translation Workflow

### Step 1: Extract keys

Run the validation script (see Quality Validation) to generate a list of all keys in `en.json`.

### Step 2: AI first pass

Use Claude/GPT to translate `en.json` → target language. Prompt:

```
Translate the values in this JSON file to {language}. Keep all keys unchanged.
Keep {variable} placeholders unchanged. Keep ICU MessageFormat syntax unchanged.
Maintain the same tone: direct, technical, concise. This is a SaaS product UI.
Do not add politeness filler or formal language unless the target culture demands it.
Return valid JSON only.
```

### Step 3: Generate review sheet

```bash
python scripts/validate_i18n.py --review-csv tr
# → dashboard/static/i18n/review_tr.csv
```

Produces a CSV with columns: `key | english | translated | status | notes`

Open in Google Sheets or Excel. This is the artifact the reviewer works on.

### Step 4: Native speaker review (mandatory — no exceptions)

**AI cannot be trusted to ship translations directly.** Common AI mistakes:

| Mistake | Example | Impact |
|---------|---------|--------|
| Over-formal register | Turkish: `siz` (formal) when product uses `sen` (informal) | Feels like a government form, not a SaaS |
| Literal translation of idioms | "Drop" a database → Turkish: `düşürmek` (physically drop) | Confusing |
| Wrong context | "Save" (disk) → "Tasarruf" (save money) instead of "Kaydet" | Wrong action |
| Untranslated jargon | Translates "API" to target language | Technical users expect "API" |
| Vowel harmony errors (Turkish) | Wrong suffix: `-ı` instead of `-i` | Grammatically incorrect |
| Honorific mismatch (Japanese) | Wrong politeness level for SaaS context | Culturally inappropriate |
| False cognates | "Actual" (EN) → "Actual" (ES, means "current") | Wrong meaning |

**Review process:**

1. Reviewer opens the CSV from Step 3
2. For each row, checks: natural? correct context? short enough for UI? technical terms standard?
3. Marks issues in the `notes` column, changes `status` to `FIX`
4. Returns CSV. Developer applies fixes to the JSON file.
5. **Gate: no language ships without a reviewed CSV on record.**

**Who reviews:**

| Language | Reviewer | Notes |
|----------|----------|-------|
| Turkish | Founder | Home market, can review personally |
| Spanish | Native speaker (freelancer or community) | Latam Spanish, not Castilian |
| Portuguese | Native speaker (Brazilian Portuguese) | BR dialect matters |
| Japanese | Professional translator or native dev | Cultural expectations highest |
| Indonesian | Native speaker | Standard Bahasa |

**Cost:** $50-150 per language for a freelance review of ~250 strings. Cheaper than shipping wrong translations and losing users.

### Step 5: Integration test

Load the language in the browser. Walk through every page. Check:
- No text overflow or clipping
- No broken layout
- All variables interpolate correctly (`{count}`, `{video_id}` render as values, not raw)
- Dates/numbers format correctly for the locale
- No missing translations (loader shows English fallback — check browser console for `[i18n] Fallback` warnings)
- Confirm dialogs read naturally (these are the most visible strings)
- Button labels fit without truncation

---

## Quality Validation

### Validation script: `scripts/validate_i18n.py` (implemented)

Three levels of automated quality checks, powered by **Kilo CLI** (routes to Grok, Gemini, Claude, or any model via Kilo's model router — no separate API keys needed):

```bash
python scripts/validate_i18n.py                    # Level 1: structural (free, instant)
python scripts/validate_i18n.py --validate tr      # Level 1 + 2 + 3 via Kilo CLI
python scripts/validate_i18n.py --review-csv tr    # Generate CSV for human review
```

### Kilo CLI Integration

The validator uses [Kilo CLI](https://kilocode.ai) (`kilo run`) for Levels 2 and 3. Kilo routes to the best available LLM — no OpenAI/Anthropic API keys required. The script auto-discovers the `kilo` binary from Windsurf/VS Code extensions or PATH.

**Model selection per language** (configurable via `KILO_I18N_MODEL` env var):

| Language | Default model | Why |
|----------|--------------|-----|
| Turkish | `kilo/x-ai/grok-4.3` | Grok has excellent Turkish — caught 20 register errors (siz→sen) in first run |
| Spanish | `kilo/~google/gemini-pro-latest` | Gemini Pro caught "Probar"→"Inspeccionar" (probe vs test), "Escaneo"→"Limpieza" (sweep vs scan) |
| Portuguese (BR) | `kilo/~google/gemini-pro-latest` | Caught "trabalhos"→"jobs", "enviar"→"upload" (BR tech users keep English terms) |
| Japanese | `kilo/anthropic/claude-sonnet-4.6` | Highest cultural sensitivity needed |
| Indonesian | `kilo/~google/gemini-pro-latest` | Standard Bahasa, good coverage |

Override: `KILO_I18N_MODEL="kilo/x-ai/grok-4.3" python scripts/validate_i18n.py --validate tr`

### How Kilo validation works

**Level 1 — Structural (free, CI/CD):**
- All en.json keys exist in target (missing = build fail)
- No extra keys in target
- All `{variable}` placeholders preserved
- No empty string values
- `_meta.completeness` matches actual key ratio

**Level 2 — Back-translation via Kilo (~$0.00, uses Kilo free tier):**
- Sends target-language strings to Kilo with prompt: "Back-translate to English"
- Kilo routes to the configured model (Grok/Gemini/Claude)
- Script compares back-translated English with original English
- Word overlap < 30% = `SEMANTIC_DRIFT` warning
- Samples 30 highest-priority strings (auth, nav, common, failure reasons)

Example output:
```
SEMANTIC_DRIFT: nav.batch
  Original EN: Batch
  TR: Toplu İşlem
  Back to EN: Bulk Actions
  Overlap: 0%
```
(This is a false positive — "Toplu İşlem" is correct Turkish for "Batch Processing". Back-translation simplifies it.)

**Level 3 — Native-speaker critique via Kilo (~$0.00, uses Kilo free tier):**
- Sends all translated strings to Kilo with context: product name, tone (direct/technical), register (informal)
- Kilo model role-plays as a native speaker reviewing UI translations
- Returns structured JSON: `{key, type, problem, fix}` for each issue
- Issue types: WRONG_MEANING, WRONG_REGISTER, UNNATURAL, TOO_LONG, WRONG_TECHNICAL_TERM, GRAMMAR
- **Script auto-applies all suggested fixes** to the JSON file

Example output (Turkish, Grok):
```
WRONG_REGISTER: auth.welcome_back
  Problem: Uses formal 'siz' register ('Hoş Geldiniz') instead of informal 'sen'
  Fix: Tekrar hoş geldin

WRONG_REGISTER: queue.confirm_retry
  Problem: Formal 'istiyor musunuz?' instead of informal 'istiyor musun?'
  Fix: Bu başarısız işi tekrar denemek istiyor musun? (Ek kredi alınmayacak)
```

Example output (Spanish, Gemini Pro):
```
WRONG_MEANING: admin.probe_video
  Problem: 'Probe' in software means to 'inspect' (Inspeccionar), not 'test' (Probar)
  Fix: Inspeccionar un video (depuración)

WRONG_TECHNICAL_TERM: nav.batch
  Problem: "Lote" is less common than "Batch" for UI navigation in technical products
  Fix: Batch
```

### The full Kilo-powered workflow

```
1. Coder AI (Claude/Cursor) generates initial translation
   └── AI translates en.json → tr.json (fast, ~90% accurate)

2. python scripts/validate_i18n.py --validate tr
   ├── Level 1: Structural check (instant)
   ├── Level 2: Kilo back-translates TR→EN via Grok
   │   └── Flags semantic drift (meaning changed)
   ├── Level 3: Kilo critiques as native Turkish speaker via Grok
   │   └── Finds register/tone/grammar issues
   │   └── Returns JSON with suggested fixes
   └── Auto-applies all fixes to tr.json
       └── "Applied 20 fix(es)"

3. Developer reviews the fixes (optional — Kilo output is high quality)

4. Ship.
```

**Real results from production (Tojlo project — case study):**
- Turkish: Grok found 34 issues across 2 runs (all `siz`→`sen` register + missing informal forms). Zero human review needed.
- Spanish: Gemini Pro found 26 issues (wrong technical terms + missing context). Zero human review needed.
- Portuguese (BR): Gemini Pro found 27 issues (kept English tech terms like "jobs", "upload", "watchlist"). Zero human review needed.
- Japanese: 264 keys still need human review (cultural expectations too high for AI-only).

**Cost: $0.00** — all via Kilo free tier. Fiverr freelancers charge $50-150 per language.
**Speed: ~60 seconds** per language. Freelancers take 2-3 days.
**Repeatable:** Run on every commit. Freelancers review once.

**When you still need a human:**
- Japanese (first launch — cultural expectations are the highest of any market)
- If Kilo critique flags >10 issues in a single run — indicates the initial AI translation was poor quality
- For marketing copy (landing pages, emails) — higher bar than UI labels

### CI/CD integration

Run `validate_i18n.py` in the final gate. Fail if:
- Any target language is below 95% completeness
- Any placeholder mismatch detected
- Any ICU syntax error

### Missing key detection at runtime

In development mode, `I18N.t()` logs missing keys to console:

```javascript
t(key, vars = {}) {
    let val = this._resolve(this._strings, key);
    if (val === undefined) {
        val = this._resolve(this._fallback, key);
        if (val === undefined) {
            console.warn(`[i18n] Missing key: ${key} (lang: ${this._lang})`);
            return key;
        }
        if (this._lang !== 'en') {
            console.info(`[i18n] Fallback to English: ${key}`);
        }
    }
    // ...
}
```

---

## String Inventory Template

When adding i18n to a new project, inventory all strings first:

| Category | How to find | Typical count |
|----------|-------------|--------------|
| Nav labels | `grep "nav-link\|nav-item" templates/` | 5-15 |
| Button labels | `grep "btn.*>" templates/` | 20-40 |
| Form labels | `grep "<label" templates/` | 15-30 |
| Placeholders | `grep "placeholder=" templates/` | 10-20 |
| Table headers | `grep "<th" templates/` | 10-25 |
| Empty states | `grep "No.*found\|No.*yet" templates/` | 3-8 |
| Confirmation dialogs | `grep "confirm(" templates/` | 5-10 |
| Toast/alert messages | `grep "toast\|alert" templates/` | 5-15 |
| Error messages | `grep "error\|Error\|failed" templates/` | 10-20 |
| Status labels | `grep "badge\|status" templates/` | 5-15 |

**YourApp count:** ~123 unique strings across 24 pages.

---

## What NOT to Translate

| Category | Why | Example |
|----------|-----|---------|
| API error messages | Keep original for debugging | `"SoftTimeLimitExceeded()"` |
| Admin panel | Internal tool, always English | `/admin` |
| Log messages | Ops team reads English logs | `logger.info(...)` |
| Technical identifiers | Must be stable | video_id, channel_id |
| DB enum values | Code depends on them | `terminal_reason='deleted'` |
| Brand names | Legal / trademark | "YourBrand" |
| Code/CLI output | Developer-facing | `--video-id`, `SELECT 1` |

Translate only the **UI label** that maps to a technical value. The value itself stays English.

---

## Rollout Plan

| Phase | Scope | Languages | Effort | Deliverable |
|-------|-------|----------|--------|-------------|
| 0 | Build system | `en` only | 4-5h | `i18n.js` + `en.json` + `data-i18n` attributes on all 24 templates + language switcher + validation script |
| 1 | Home market test | `tr` | 2h | `tr.json` + native review + layout test |
| 2 | Tier 1 markets | `es`, `pt-BR` | 4h | 2 JSON files + review + expansion layout test |
| 3 | High-value market | `ja` | 3h | `ja.json` + native review (mandatory) + Kanji rendering test |
| 4 | Volume market | `id` | 2h | `id.json` + review |
| **Total** | | **6 languages** | **~15-17h** | |

---

## Checklist

### Before starting i18n (Phase 0)

- [ ] All templates use `<meta charset="UTF-8">`
- [ ] No hardcoded date/number formats (use `Intl` APIs)
- [ ] Buttons use `min-width` or flex, not fixed `width`
- [ ] Tables wrapped in `table-responsive`
- [ ] `en.json` created with all user-facing strings inventoried

### Per-language launch

- [ ] JSON file created and validated (`validate_i18n.py` passes)
- [ ] All `{variable}` placeholders preserved
- [ ] ICU plural forms correct for the language
- [ ] Native speaker reviewed (mandatory for `ja`, recommended for all)
- [ ] Layout tested at target language (no overflow, no clipping)
- [ ] Date/number formatting correct (`Intl` locale matches)
- [ ] Language switcher shows the new option
- [ ] Cookie persistence works (switch → reload → stays)

### Ongoing maintenance

- [ ] New strings added to `en.json` first, then to all target files
- [ ] `validate_i18n.py` runs in CI/CD pipeline
- [ ] Completeness tracked per language in `_meta.completeness`
- [ ] Translator notified when new keys are added (diff `en.json` between releases)

---

## Anti-Patterns (production killers)

These mistakes are discovered in production after translators deliver, when it's expensive to fix.

### 1. String concatenation

**Broken:**
```javascript
label = "You have " + count + " credits remaining";
```

Translators see three fragments: `"You have "`, `count`, `"credits remaining"` — they can't reorder. Japanese puts the number at the end. Turkish puts it in the middle. German puts the verb at the end of subordinate clauses.

**Fixed:**
```javascript
label = I18N.t('common.credits_remaining', { count: count });
// en.json: "You have {count} credits remaining"
// ja.json: "残り{count}クレジット"
// tr.json: "{count} krediniz kaldi"
```

### 2. Splitting sentences across elements

**Broken:**
```html
<span>Click </span><a href="/here">here</a><span> to continue</span>
```

Translator gets 3 strings. Can't form a natural sentence.

**Fixed:**
```html
<span data-i18n-html="common.click_to_continue">Click <a href="/here">here</a> to continue</span>
```
```json
{ "common.click_to_continue": "Click <a href=\"/here\">here</a> to continue" }
```

Or better — restructure so the link wraps the full action:
```html
<a href="/here" data-i18n="common.continue_link">Continue</a>
```

### 3. Assuming word order

**Broken:**
```javascript
msg = userName + "'s " + itemName;  // "John's Project"
```

Possessive works differently in every language. Japanese: `ジョンのプロジェクト`. Turkish: `John'un Projesi`.

**Fixed:**
```json
{ "project.owned_by": "{owner} — {name}" }
```

### 4. Hardcoded plurals

**Broken:**
```javascript
label = count === 1 ? "1 item" : count + " items";
```

English has 2 plural forms. Arabic has 6. Russian has 4. Czech has 3.

**Fixed:** ICU MessageFormat (see earlier section).

### 5. Images with embedded text

Screenshots, diagrams, or icons with English text baked in cannot be translated. Use SVG with text elements or CSS-styled `<span>` overlays instead.

### 6. Assuming Latin character width

Japanese and Chinese characters are full-width (2x the width of Latin). A column sized for "Status" will overflow with "ステータス". Use `min-width`, not `width`.

### 7. No context for translators

The key `"save"` could mean "save a file", "save money", or "save a life" — three different words in most languages. Add context:

```json
{
  "common.save_button": "Save",
  "_context": {
    "common.save_button": "Button to save form changes, not financial saving"
  }
}
```

Or use a `_context` sibling in the JSON that the loader ignores but translators see.

---

## Email and Notification Localization

Transactional emails (password reset, verification, job completion alerts) must also be localized.

### Architecture

```
dashboard/
├── templates/
│   └── email/
│       ├── base_email.html          # Shared email layout
│       ├── password_reset.html      # Jinja template with i18n keys
│       └── job_complete.html
└── static/
    └── i18n/
        ├── en.json                  # includes "email" namespace
        └── tr.json
```

### Implementation

Emails are server-rendered (Jinja), not client-rendered. Use a thin Python helper:

```python
import json
from pathlib import Path

_TRANSLATIONS = {}

def load_translations(lang: str) -> dict:
    if lang not in _TRANSLATIONS:
        path = Path(f'dashboard/static/i18n/{lang}.json')
        if path.exists():
            _TRANSLATIONS[lang] = json.loads(path.read_text())
        else:
            _TRANSLATIONS[lang] = load_translations('en')
    return _TRANSLATIONS[lang]

def t(key: str, lang: str = 'en', **vars) -> str:
    strings = load_translations(lang)
    val = key
    for k in key.split('.'):
        strings = strings.get(k, {}) if isinstance(strings, dict) else key
    if isinstance(strings, str):
        val = strings
        for k, v in vars.items():
            val = val.replace(f'{{{k}}}', str(v))
    return val
```

Usage in email template:
```html
<h1>{{ t('email.password_reset_subject', lang=user_lang) }}</h1>
<p>{{ t('email.password_reset_body', lang=user_lang, name=user.display_name) }}</p>
```

### Email JSON keys

```json
{
  "email": {
    "password_reset_subject": "Reset your password",
    "password_reset_body": "Hi {name}, click the link below to reset your password.",
    "password_reset_button": "Reset Password",
    "verification_subject": "Verify your email",
    "verification_body": "Hi {name}, click below to verify your email address.",
    "job_complete_subject": "{count} jobs completed",
    "job_complete_body": "Your batch of {count} videos has finished processing."
  }
}
```

---

## SEO and URL Strategy

### For authenticated SaaS dashboards (our case)

Dashboard pages are behind auth — search engines don't crawl them. Client-side i18n is sufficient. No hreflang, no subfolder URL structure needed.

### For public-facing pages (future: landing, pricing, docs)

When public pages are multilingual, use **subfolder** URL structure:

| Strategy | URL | SEO impact |
|----------|-----|-----------|
| Subfolder (recommended) | `yourapp.com/es/pricing` | Consolidates domain authority |
| Subdomain | `es.yourapp.com/pricing` | Splits authority (avoid) |
| ccTLD | `yourapp.es/pricing` | Per-country (expensive, complex) |

**Hreflang requirements** (non-negotiable for public pages):

```html
<link rel="alternate" hreflang="en" href="https://yourapp.com/pricing" />
<link rel="alternate" hreflang="es" href="https://yourapp.com/es/pricing" />
<link rel="alternate" hreflang="pt-BR" href="https://yourapp.com/pt-br/pricing" />
<link rel="alternate" hreflang="x-default" href="https://yourapp.com/pricing" />
```

Rules:
1. Every page must self-reference
2. All annotations must be symmetric (page A → B AND B → A)
3. Use valid ISO 639-1 language codes
4. Include `x-default` for the canonical (English) version
5. Sitemap must include all locale variants

**Not needed now** — our dashboard is authenticated. Add when public marketing pages go multilingual.

---

## Testing Strategy

### Level 1: Automated validation (CI/CD)

Run `scripts/validate_i18n.py` on every commit:

```
- All en.json keys exist in every target file
- No orphan keys in target files
- All {variable} placeholders preserved
- ICU syntax valid (balanced braces)
- No empty values
- No HTML in non-_html keys
- _meta.completeness matches actual ratio
```

### Level 2: Pseudo-localization (development)

Generate a pseudo-locale that expands strings ~35% and adds accents:

```javascript
function pseudoLocalize(str) {
    // Skip variables like {count}
    return str.replace(/([^{]+)(?=\{|$)/g, (match) => {
        const accented = match.replace(/[aeiou]/gi, c => {
            const map = {a:'a',e:'e',i:'i',o:'o',u:'u',A:'A',E:'E',I:'I',O:'O',U:'U'};
            return (map[c] || c) + '\u0301';
        });
        return '[' + accented + '~]';
    });
}
```

**What it catches:** text overflow, clipping, layout breakage, hardcoded strings that weren't tagged with `data-i18n` (they'll be the only ones without `[a' ccents~]`).

### Level 3: Visual regression (per-language launch)

For each language, capture screenshots of all 24 pages and compare against English baseline:

```bash
# Using Playwright
for lang in en tr es pt-br ja id; do
    npx playwright test --project=screenshots --env LANG=$lang
done
```

Alternatively, manual walkthrough with the checklist:
- [ ] Login page
- [ ] Register page
- [ ] Queue (all 5 tabs)
- [ ] Watchlists (with data)
- [ ] Library
- [ ] Settings
- [ ] Pricing
- [ ] Modals (open each one)
- [ ] Error page
- [ ] Empty states

### Level 4: Native speaker smoke test

Give a native speaker a 10-minute task: "Log in, check your queue, star a channel, view a transcript." They report anything that sounds unnatural, is confusing, or looks broken.

---

## Production Gotchas (learned from industry)

| Gotcha | Impact | Prevention |
|--------|--------|-----------|
| **Flash of English** — page loads in English, then flips to target language | Users see a jarring content shift | Keep English as default text in HTML; i18n.js replaces fast enough (<100ms). Or use `visibility: hidden` until init completes. |
| **Stale translations** — new feature ships, translator not notified | New strings show in English while rest is translated | `validate_i18n.py` blocks deploy if completeness < 95%. Diff `en.json` on each release. |
| **Gender agreement** — "Your file was deleted" needs feminine form in some languages | Grammatically wrong translations | Use ICU select or provide gender-neutral phrasing in English. |
| **Number formatting in ICU** — `{count}` outputs "1,234" in English but "1.234" in German | Wrong-looking numbers | Use `Intl.NumberFormat` for display; keep ICU `{count}` as raw integer. |
| **Cache poisoning** — CDN serves French JSON to an English user | Wrong language for the session | Set `Cache-Control: private` on i18n JSON files, or bust cache with version query param: `en.json?v=1.0.0`. |
| **3x cost of retrofitting** — adding i18n after 50K lines of code | Weeks of find-and-replace | Build i18n from day one (this doc exists to prevent this). |
| **Locale cookie on public pages** — Google crawls with `lang=tr` cookie and indexes Turkish | Wrong language indexed for English queries | Public pages: use URL structure (`/es/pricing`), not cookies. Cookies for authenticated dashboard only. |

---

## References

- [JSON Translation Files: Formats, Structure, and Best Practices](https://better-i18n.com/en/blog/json-translation-files/)
- [ICU Message Format Guide (Crowdin)](https://crowdin.com/blog/icu-guide)
- [SaaS Localization: How to Translate Software in 2026 (Crowdin)](https://crowdin.com/blog/saas-localization)
- [i18n Key Naming for Longevity and Sanity (Locize)](https://www.locize.com/blog/guide-to-i18n-key-naming/)
- [Best Practices in Software Localization (SimpleLocalize)](https://simplelocalize.io/blog/posts/best-practices-in-software-localization/)
- [i18n for SaaS Teams (SimpleLocalize)](https://simplelocalize.io/blog/posts/i18n-for-saas-teams/)
- [i18n-lint: Lint tool for translation files (GitHub)](https://github.com/levkorsy/i18n-lint)
- [Internationalization Complete Guide (SimpleLocalize)](https://simplelocalize.io/blog/posts/internationalization-guide-software-localization/)
- [String Concatenation Anti-Pattern (AMP)](https://github.com/ampproject/amphtml/issues/38060)
- [i18n Best Practices: Keep It Together](https://localization.blog/2022/05/16/i18n-best-practices-keep-it-together/)
- [Pseudo-localization for Automated i18n Testing](https://dev.to/anton_antonov/pseudo-localization-for-automated-i18n-testing-31)
- [i18n SEO: Hreflang Tags and Locale URLs Guide](https://better-i18n.com/en/blog/i18n-seo-hreflang-locale-urls-guide/)
- [Localizing Transactional Email Templates (Python)](https://camillovisini.com/coding/python-i18n-localizing-email-templates)
- [Linguistics for Developers: Real-World i18n Challenges (Phrase)](https://phrase.com/blog/posts/internationalization-beyond-code-a-developers-guide-to-real-world-language-challenges/)
- [From Days to Minutes: i18n Workflow with AI and GitHub Actions](https://medium.com/fsmk-engineering/from-days-to-minutes-how-we-revolutionized-our-i18n-workflow-with-ai-and-github-actions-e14219588cb5)

- [JSON Translation Files: Formats, Structure, and Best Practices](https://better-i18n.com/en/blog/json-translation-files/)
- [ICU Message Format Guide (Crowdin)](https://crowdin.com/blog/icu-guide)
- [SaaS Localization: How to Translate Software in 2026 (Crowdin)](https://crowdin.com/blog/saas-localization)
- [i18n Key Naming for Longevity and Sanity (Locize)](https://www.locize.com/blog/guide-to-i18n-key-naming/)
- [Best Practices in Software Localization (SimpleLocalize)](https://simplelocalize.io/blog/posts/best-practices-in-software-localization/)
- [i18n for SaaS Teams (SimpleLocalize)](https://simplelocalize.io/blog/posts/i18n-for-saas-teams/)
- [i18n-lint: Lint tool for translation files (GitHub)](https://github.com/levkorsy/i18n-lint)
- [Internationalization Complete Guide (SimpleLocalize)](https://simplelocalize.io/blog/posts/internationalization-guide-software-localization/)
