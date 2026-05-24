# Mobile-First Responsive Testing Guide

**Purpose:** Single source of truth for mobile-first responsive design testing across all Fabrik web projects. Self-contained — AI coding agents need only this file.

**Minimum viewport:** 375px (iPhone SE in Chrome DevTools)

**Canonical source:** All responsive rules (RWD1–RWD10), breakpoints, component behavior tables, fix patterns, testing procedures, and the agent directive live here. Rule packs (`ocoron-design-system.md`, `60-saas-ui.md`, `tojlo-design-system.md`) reference this document for responsive testing — do not duplicate testing procedures in those files.

---

## Responsive Rules (RWD1–RWD10)

Canonical rules from `ocoron-design-system.md` § Responsive Layout. Reproduced here so this doc is self-contained.

| Rule | Requirement |
|---|---|
| **RWD1** | Every web page must be functional and readable at 375px. No horizontal scrollbar on the page body. (Exception: data tables using horizontal scroll pattern.) |
| **RWD2** | Touch targets >= 44px on viewports < 1024px, even in web browsers. |
| **RWD3** | Text readable without horizontal scrolling or zoom at any viewport. No fixed-width containers that overflow. |
| **RWD4** | Navigation accessible at every breakpoint. Hidden nav requires a visible toggle (hamburger or bottom tabs). |
| **RWD5** | Images and media never overflow their container. `max-width: 100%; height: auto;` as baseline. |
| **RWD6** | No `display: none` to hide critical content on mobile. Reorganize, don't remove. |
| **RWD7** | Minimum 14px body text on all viewports. |
| **RWD8** | Modals become full-screen sheets on viewports < 640px. |
| **RWD9** | Sidebar navigation MUST collapse on viewports < 1024px. Icon rail at 768–1023px, hidden below 768px. |
| **RWD10** | Test every page at 375px, 768px, 1440px before merge. Untested responsive = broken responsive. |

---

## Breakpoints

| Token | Width | Tailwind | Target |
|---|---|---|---|
| `--bp-sm` | 640px | `sm:` | Large phones (landscape), small tablets |
| `--bp-md` | 768px | `md:` | Tablets (portrait). Sidebar collapses here. |
| `--bp-lg` | 1024px | `lg:` | Tablets (landscape), small laptops. Full sidebar. |
| `--bp-xl` | 1280px | `xl:` | Laptops, desktops |
| `--bp-2xl` | 1536px | `2xl:` | Large desktops, ultrawide |

---

## Component Behavior by Viewport

| Component | < 768px | 768px – 1023px | 1024px+ |
|---|---|---|---|
| **Sidebar nav** | Hidden; hamburger or bottom tabs | Collapsed icon rail (56px) | Full sidebar (240px) |
| **Data tables** | Card list (one card per row) OR horizontal scroll with sticky first column | Horizontal scroll with sticky first column | Full table |
| **Dashboard grid** | 1 column, stacked cards | 2 columns | 3-4 columns |
| **Forms** | Single column, full width | Single column, max-width 560px centered | Two-column for grouped fields |
| **Modal/dialog** | Full-screen sheet | Centered modal, max-width 480px | Centered modal, max-width 560px |
| **Hero section** | Stack vertically, image below text | Stack vertically | Side-by-side |
| **Top navigation** | Logo + hamburger | Logo + condensed nav | Logo + full nav + actions |
| **Filter bars** | "Filters" button → sheet/drawer | Inline, stacked if needed | Inline horizontal |

---

## Principle: Screenshot First, Fix Second

Never guess what's broken. Take automated screenshots at every target viewport, read them, then fix only what's actually wrong. Most agents waste cycles fixing imaginary issues or applying broad CSS that breaks desktop.

---

## Target Viewports

| Width | Device | Chrome DevTools preset | Purpose |
|---|---|---|---|
| **375px** | iPhone SE | "iPhone SE" | Design floor — smallest current phone |
| **768px** | iPad portrait | "iPad Mini" | Tablet / sidebar collapse threshold |
| **1024px** | iPad landscape / small laptop | — (set manually) | Full sidebar threshold |
| **1440px** | Standard desktop | — (set manually) | Default desktop |

These match `ocoron-design-system.md` § Responsive Testing Checklist.

---

## Step 1: Set Up Playwright for Automated Screenshots

### Install

```bash
# In project .venv or node_modules
pip install playwright Pillow && playwright install chromium
# OR
npm install -D @playwright/test
```

### Login Helper (authenticated SaaS pages)

```python
# scripts/mobile_test_login.py
from playwright.sync_api import sync_playwright
import os

def create_mobile_session(width=375, height=812):
    """Returns (playwright, browser, context, page) with mobile viewport + logged-in session."""
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    page.goto(f"{base_url}/login")
    page.wait_for_load_state("networkidle")

    # Adjust selectors for your auth form
    page.fill('input[type="email"]', os.getenv("TEST_EMAIL", "test@example.com"))
    page.fill('input[type="password"]', os.getenv("TEST_PASSWORD", "testpass"))
    page.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    return p, browser, context, page
```

---

## Step 2: Screenshot Every Page at Every Viewport

```python
# scripts/screenshot_responsive.py
from playwright.sync_api import sync_playwright
import os

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
OUTPUT_DIR = "/tmp/responsive"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define your project's pages
PAGES = [
    ("/", "home", 3),
    ("/dashboard", "dashboard", 3),
    ("/settings", "settings", 2),
    # Add all project pages here
]

VIEWPORTS = [
    (375, 812, "375"),
    (768, 1024, "768"),
    (1440, 900, "1440"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for vw, vh, label in VIEWPORTS:
        context = browser.new_context(viewport={"width": vw, "height": vh})
        page = context.new_page()

        # Login (adjust for your app)
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        page.fill('input[type="email"]', os.getenv("TEST_EMAIL", "test@example.com"))
        page.fill('input[type="password"]', os.getenv("TEST_PASSWORD", "testpass"))
        page.locator('button[type="submit"]').click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        for url, name, wait in PAGES:
            try:
                page.goto(f"{BASE_URL}{url}", timeout=15000)
                page.wait_for_timeout(wait * 1000)
                page.screenshot(path=f"{OUTPUT_DIR}/{label}_{name}.png", full_page=True)
                print(f"  {label}px {name}: OK")
            except Exception as e:
                print(f"  {label}px {name}: FAIL - {str(e)[:60]}")

        context.close()
    browser.close()
```

### Splitting Tall Screenshots

Full-page captures of long lists exceed what most AI models can process. Split them:

```python
from PIL import Image

def split_screenshot(path, max_height=1800):
    img = Image.open(path)
    w, h = img.size
    if h <= max_height:
        return
    chunks = (h + max_height - 1) // max_height
    for i in range(chunks):
        top = i * max_height
        bottom = min((i + 1) * max_height, h)
        img.crop((0, top, w, bottom)).save(path.replace(".png", f"_part{i+1}.png"))
```

---

## Step 3: Screenshot Interactive States

Static pages are not enough. Capture the states users actually see:

```python
# Modals / dialogs
page.locator('button:has-text("Create")').first.click()
page.wait_for_timeout(1000)
page.screenshot(path=f"{OUTPUT_DIR}/375_modal.png")

# Search with results
page.fill('[type="search"]', "test query")
page.wait_for_timeout(2000)
page.screenshot(path=f"{OUTPUT_DIR}/375_search_results.png")

# Tables with data loaded (not empty state)
page.goto(f"{BASE_URL}/data?limit=50")
page.wait_for_timeout(3000)
page.screenshot(path=f"{OUTPUT_DIR}/375_table_data.png")

# Hamburger / mobile menu open
hamburger = page.locator('[aria-label="Menu"], .navbar-toggler, [data-sidebar-toggle]')
if hamburger.count() > 0 and hamburger.first.is_visible():
    hamburger.first.click()
    page.wait_for_timeout(500)
    page.screenshot(path=f"{OUTPUT_DIR}/375_menu_open.png")

# Dropdown menus
page.locator('[data-dropdown], .dropdown-toggle').first.click()
page.wait_for_timeout(500)
page.screenshot(path=f"{OUTPUT_DIR}/375_dropdown.png")
```

---

## Step 4: Diagnose from Screenshots

Read each screenshot and check against this table:

| Issue | What to look for | Fix pattern |
|---|---|---|
| **Horizontal overflow** | Content wider than viewport, horizontal scrollbar | `max-width: 100%` on the specific element, or `overflow-x: auto` on the container |
| **Overlapping elements** | Elements on top of each other | `flex-direction: column` on the specific container (not globally on all `.flex`) |
| **Clipped text** | Text cut off at container edge | `word-break: break-word` or `overflow-wrap: break-word` on the element |
| **Tiny text** | Text smaller than 13px | Increase font-size. If it doesn't fit at 13px, remove content — never shrink below 13px |
| **Buttons too small** | Touch target under 44px | Increase padding. Minimum 44x44px tap area |
| **Wide tables** | Columns don't fit 375px | Wrap in scrollable container (horizontal scroll is acceptable) OR transform to card list |
| **Long labels** | Labels wrap to 2+ lines breaking layout | Truncate with ellipsis, or shorten text. Check i18n files if text is localized |
| **Fixed pixel widths** | `style="width: 250px"` exceeds viewport | `max-width: 100%` on the specific element — never use a global `[style*="width:"]` selector |
| **Sidebar visible** | Full sidebar showing below 768px | Should be hidden (hamburger/overlay). Check media query or framework collapse class |
| **Modal overflow** | Modal wider than viewport | Modal should become full-screen sheet below 640px. Add `max-width: calc(100vw - 1rem)` |
| **Navbar overflow** | Right-side items wrapping or clipped | Hide text labels on mobile, show icons only. Use framework responsive visibility classes |

---

## Step 5: Fix Patterns by Framework

### Next.js + Tailwind (saas-skeleton)

```tsx
{/* Stack on mobile, row on desktop */}
<div className="flex flex-col md:flex-row gap-2 md:gap-4">

{/* Hide on mobile */}
<span className="hidden md:inline">Full label text</span>

{/* Table → card on mobile */}
<div className="hidden md:block">  {/* Desktop table */}
  <table>...</table>
</div>
<div className="md:hidden">  {/* Mobile cards */}
  {items.map(item => <Card key={item.id} {...item} />)}
</div>

{/* Modal → sheet on mobile */}
<Dialog>
  <DialogContent className="sm:max-w-md max-sm:fixed max-sm:inset-x-0 max-sm:bottom-0 max-sm:top-auto max-sm:rounded-b-none">
```

### Bootstrap 5 (legacy / Jinja templates)

```html
<!-- Stack on mobile, row on desktop -->
<div class="d-flex flex-column flex-md-row gap-1 gap-md-3">

<!-- Hide on mobile -->
<span class="d-none d-md-inline">Full label text</span>

<!-- Table horizontal scroll -->
<div class="table-responsive">
  <table class="table">...</table>
</div>

<!-- Cards: 1 per row mobile, 4 per row desktop -->
<div class="col-12 col-md-6 col-lg-3">
```

### CSS-only (any framework)

```css
@media (max-width: 768px) {
    /* Scope to specific components — NEVER use broad selectors */
    .dashboard-grid { grid-template-columns: 1fr; }

    /* Modal → full-width */
    .modal-dialog {
        margin: 0.5rem;
        max-width: calc(100vw - 1rem);
    }

    /* Sidebar collapse */
    .sidebar { display: none; }
    .sidebar.open { display: block; position: fixed; z-index: 50; }
}
```

---

## Step 6: Re-Screenshot and Verify

After applying fixes, re-run the screenshot script and compare before/after.

**Per-page checklist (RWD1–RWD10):**

- [ ] No horizontal scrollbar on the page body at 375px
- [ ] All text readable without zooming (minimum 13px body, 14px per design system)
- [ ] All buttons/links tappable (minimum 44px touch target)
- [ ] Tables either transform to cards OR scroll horizontally inside their container
- [ ] Modals render as full-screen sheets below 640px
- [ ] Sidebar hidden below 768px (hamburger or overlay menu available)
- [ ] Navigation accessible at every viewport (visible toggle if collapsed)
- [ ] Forms usable: inputs full-width, labels visible, submit button not hidden
- [ ] Cards stack properly (1-2 per row, not squeezed side-by-side)
- [ ] No content removed — reorganized for mobile, not deleted

---

## Step 7: Test Primary User Flow

The most important test: can a user complete their core task on a phone?

```python
# Define your project's primary flow
FLOW_STEPS = [
    ("Navigate to create", lambda p: p.click('a:has-text("New")')),
    ("Fill form", lambda p: [p.fill("#name", "Test"), p.fill("#email", "a@b.com")]),
    ("Submit", lambda p: p.click('button[type="submit"]')),
    ("Verify success", lambda p: p.wait_for_selector('.toast-success, [role="alert"]')),
]

for step_name, action in FLOW_STEPS:
    try:
        action(page)
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUTPUT_DIR}/375_flow_{step_name.replace(' ', '_')}.png")
        print(f"  Flow: {step_name} OK")
    except Exception as e:
        print(f"  Flow: {step_name} FAIL - {str(e)[:60]}")
        page.screenshot(path=f"{OUTPUT_DIR}/375_flow_{step_name.replace(' ', '_')}_FAIL.png")
        break
```

---

## Common Mistakes

### 1. Broad CSS selectors cause cascading breakage

**Bad:** `[style*="width:"] { max-width: 100% !important; }` — breaks thumbnails, avatars, color pickers, dropdowns.

**Good:** Target specific elements: `#filterPanel input[style*="width:"]`

### 2. JS-rendered tables need column hiding in BOTH places

If a table has static `<th>` headers but JS-rendered `<td>` cells, hiding `<th>` without matching the JS template causes column misalignment.

### 3. i18n overrides HTML text

`data-i18n="key"` (or `t('key')` in React) replaces text at runtime. Changing HTML/JSX without updating the i18n JSON has zero effect on the rendered page.

### 4. Don't remove features for mobile

Horizontal scroll on tables is acceptable. Hiding columns removes useful information. Users chose a data-heavy SaaS — they expect data density. Reorganize, don't delete.

### 5. `!important` escalation

If your framework uses `!important` on utility classes (Tailwind `!`, Bootstrap `p-0`), your override needs specificity, not more `!important`. Use `:not()` exclusions or more specific selectors.

### 6. Test with real data, not empty states

Empty pages always look fine at 375px. Test with 100+ items in tables, long names, 6-digit numbers in stat cards.

### 7. Desktop must remain untouched

All mobile fixes go inside `@media (max-width: ...)` blocks or use framework responsive prefixes (`md:`, `d-md-*`). If a desktop regression appears after your mobile fix, you scoped too broadly.

---

## Verification Checklist

Before claiming mobile-responsive, every page must have a screenshot at 375px and pass the checklist:

```
Page                    | 375px | 768px | 1440px | Flow tested
------------------------|-------|-------|--------|------------
Login / Register        |   ?   |   ?   |   ?    |     ?
Home / Dashboard        |   ?   |   ?   |   ?    |     ?
Primary feature page    |   ?   |   ?   |   ?    |     ?
Data table page         |   ?   |   ?   |   ?    |     ?
Settings                |   ?   |   ?   |   ?    |     ?
Search / Filter         |   ?   |   ?   |   ?    |     ?
Create / Edit form      |   ?   |   ?   |   ?    |     ?
Modal / Dialog          |   ?   |   ?   |   ?    |     ?
Menu / Navigation       |   ?   |   ?   |   ?    |     ?
Primary user flow       |  n/a  |  n/a  |  n/a   |     ?
```

Replace `?` with `OK` or `FAIL`. Every cell must be `OK` before the PR merges.

---

## Agent Directive (copy-paste for coding agents)

> **Responsive floor is 375px (iPhone SE in Chrome DevTools).** Apply these rules at viewports below 768px:
>
> 1. Tables → card list OR horizontal scroll with sticky first column. Never squeeze desktop columns.
> 2. Sidebar → hidden. Hamburger or overlay menu.
> 3. Long text → truncate with ellipsis (single line). Full text on detail screen.
> 4. Font floor 13px. If it doesn't fit at 13px, remove content — don't shrink.
> 5. Card padding 8px (not 16px) on mobile viewports.
> 6. Side-by-side elements that don't fit → stack vertically.
> 7. Filter bars → "Filters" button opening a sheet/drawer.
> 8. Modals → full-screen sheets below 640px.
> 9. Test in Chrome DevTools → iPhone SE (375x667).
> 10. Desktop must remain untouched — all changes inside media queries or responsive prefixes.
