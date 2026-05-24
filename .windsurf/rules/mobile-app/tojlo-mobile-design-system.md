---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*", "**/app.json", "**/eas.json"]
description: Tojlo Mobile Design System — module-aware mobile component patterns extending ocoron-mobile-design-system.md
trigger: glob
---
<!-- CONSUMER: Coding agents building Tojlo React Native mobile UI
     GOAL: Module-aware mobile patterns — module switcher, module cards, operator dashboards, embedded frames
     TRAYCER USAGE: Injects as Context File for Tojlo mobile client-lane UI tickets.
     AGENT USAGE: Use alongside ocoron-mobile-design-system.md and tojlo-design-system.md. This file specifies Tojlo mobile deltas only. -->

# Tojlo Mobile Design System

> Mobile-specific component patterns for the Tojlo B2B operating system. Extends `ocoron-mobile-design-system.md` — all generic mobile patterns (list items, bottom sheets, action sheets, search, navigation headers, onboarding, form inputs) are inherited unchanged. This file adds **Tojlo-specific mobile patterns** for modules, operator dashboards, and embedded frames.

**Inheritance chain:**
1. `ocoron-design-system.md` — all tokens (colors, typography, spacing, motion)
2. `tojlo-design-system.md` — Tojlo brand, module naming, module color coding, verbal identity
3. `ocoron-mobile-design-system.md` — generic mobile component patterns (LI1-LI6, BS1-BS5, AS1-AS5, SR1-SR5, NH1-NH4, ON1-ON6, MF1-MF6)
4. **This file** — Tojlo-specific mobile overrides and additions

---

## Inherited Unchanged from `ocoron-mobile-design-system.md`

All 32 rules (LI1-LI6, BS1-BS5, AS1-AS5, SR1-SR5, NH1-NH4, ON1-ON6, MF1-MF6) apply without modification. The following sections are **identical** and must not be re-specified:

- List Item Anatomy (structure, heights, section headers, swipe actions)
- Bottom Sheet (structure, sizes, animation)
- Action Sheet (structure, animation)
- Mobile Search (structure, animation)
- Navigation Header (structure, large title scroll-collapse)
- Mobile Form Inputs (sizing, pickers, keyboard configuration)

Both dark and light mode are mandatory — inherited from `80-mobile.md` (OS detection via `Appearance.getColorScheme()` + manual toggle + MMKV persistence).

If a pattern is not listed in this document, the Ocoron mobile design system rule applies.

---

## 1. Module Switcher (Mobile)

The primary navigation mechanism for switching between Tojlo's 12 modules on mobile. Replaces the web sidebar's module list.

### Trigger

- Accessed via the **bottom tab bar** leftmost tab (grid icon, labeled "Modules") OR via long-press on the current module name in the navigation header.

### Structure

```
┌────────────────────────────────────┐
│          ━━━━━━━━━━━━━             │  ← drag handle
│                                    │
│  Modules                           │  ← sheet title
│                                    │
│  ┌──────┐  ┌──────┐  ┌──────┐     │
│  │ icon │  │ icon │  │ icon │     │  ← module grid (3 columns)
│  │ OPS  │  │ HUB  │  │ CHAT │     │
│  └──────┘  └──────┘  └──────┘     │
│  ┌──────┐  ┌──────┐  ┌──────┐     │
│  │ icon │  │ icon │  │ icon │     │
│  │ MAIL │  │ TI   │  │ WEB  │     │
│  └──────┘  └──────┘  └──────┘     │
│            ...                     │
└────────────────────────────────────┘
```

- Appears as a **bottom sheet (medium)** — snaps to 50%, expandable to 90%
- **Grid layout:** 3 columns, 80px per cell, 12px gap
- **Each cell:** module icon (24px, monochrome, `--text-body`) centered above module name (Inter 500, uppercase, 10px, letter-spacing 1px)
- **Layer indicator:** 3px colored dot below the module name — Core = `--color-accent`, Intelligence = `--color-purple`, Growth = `--color-secondary`
- **Active module:** icon uses `--color-accent`, name uses `--text-primary`, cell has `--color-accent-muted` background
- **Inactive module:** icon and name use `--text-muted`
- **Disabled module** (not provisioned for tenant): icon at 30% opacity, name `--text-muted`, non-tappable. No tooltip on mobile — long-press shows "Contact admin to enable [MODULE]" toast

### Animation

- Sheet enters per BS rules (`--motion-slow`, `--ease-emphasis`)
- Module selection: cell press feedback (`scale(0.95)`, light haptic), dismiss sheet, navigate to module root screen

### Module Switcher Rules

- **MS1:** The module switcher is always a bottom sheet, never a full-screen page. Operators should feel they are *switching context*, not *leaving* the app.
- **MS2:** Module order follows the canonical list from `tojlo-design-system.md` § Module Naming. Never reorder by usage frequency — consistency builds muscle memory.
- **MS3:** Module icons are monochrome. Color goes on the layer dot only — never on the icon glyph (inherited from Tojlo T3).
- **MS4:** Selecting a module navigates to that module's root screen and sets it as the active context for the bottom tab bar.

---

## 2. Module-Aware Bottom Tab Bar

The persistent bottom navigation for Tojlo mobile. Tabs change based on the active module.

### Structure

```
┌────────────────────────────────────────────────┐
│ [Modules]  [Tab 1]  [Tab 2]  [Tab 3]  [More]  │  48px + safe area
└────────────────────────────────────────────────┘
```

- **Height:** 48px content + safe area inset bottom
- **Background:** `--surface-1`
- **Border top:** 1px `--border`
- **Fixed first tab:** "Modules" (grid icon) — opens the module switcher sheet. Always present regardless of active module.
- **Tabs 1-3:** module-specific primary screens (e.g., OPS → Orders / Inventory / Suppliers). Defined per module.
- **Fixed last tab:** "More" (ellipsis icon) — opens an action sheet with: Settings, Profile, Notifications, Help. Always present.
- **Active tab:** icon + label in `--color-accent`. Inactive: `--text-muted`.
- **Labels:** Inter 500, 11px, below icon. Always visible (no icon-only tabs — operators need labels for discoverability).

### Per-Module Tab Configurations

Modules follow the canonical list from `tojlo-design-system.md` § Module Naming. Not all modules have mobile tabs — AUTH is a backend service, Dashboard is the home screen.

| Module | Tab 1 | Tab 2 | Tab 3 |
|---|---|---|---|
| **OPS** | Orders | Inventory | Suppliers |
| **HUB** | Workflows | Runs | Triggers |
| **CHAT** | Conversations | Contacts | Templates |
| **MAIL** | Inbox | Drafts | Sent |
| **PORTAL** | Pages | Access | Activity |
| **VAULT** | Documents | Folders | Shared |
| **TI** | Insights | Reports | Alerts |
| **WEB** | Pages | Media | Analytics |
| **MARKETS** | Campaigns | Audiences | Performance |
| **REACH** | Prospects | Sequences | Lists |
| **OUTREACH** | Campaigns | Templates | Analytics |

### Tab Bar Rules

- **TB1:** Maximum 5 tabs total (Modules + 3 module tabs + More). Never 6+.
- **TB2:** Tab labels are always visible — no icon-only tabs. B2B operators are not daily consumer app users; they need explicit labels.
- **TB3:** The "Modules" tab always shows a badge with the count of modules that have pending attention items (unread messages, overdue tasks, failed workflows). Badge uses `--color-danger` background, white text, max "9+".
- **TB4:** Switching modules via the module switcher updates tabs 1-3 immediately. No loading state for the tab bar itself — only the content area loads.

---

## 3. Module Card (Mobile)

Adaptation of the web Module Card for mobile dashboard grids. Used on the Tojlo Home screen.

### Structure

```
┌─────────────────────────────────────┐
│ [layer dot]  MODULE NAME       [›]  │  ← header row
│                                     │
│  KPI value          Status pill     │  ← content row
│  KPI label                          │
└─────────────────────────────────────┘
```

- Uses the inherited list item anatomy (two-line, 64px) with these overrides:
- **Leading:** 3px layer-color dot (not a module icon — too small at list-item scale)
- **Title:** module name, Inter 500, uppercase, 11px, letter-spacing 1px, `--text-primary`
- **Subtitle:** primary KPI (JetBrains Mono 400, 15px, `--text-primary`) + KPI label (Inter 400, 12px, `--text-muted`)
- **Trailing:** status pill (Active/Syncing/Error) using inherited pill pattern + chevron
- **Press:** navigates to module root (same as module switcher selection)

### Dashboard Grid (Home Screen)

```
┌────────────────────────────────────┐
│ ← Tojlo                     [🔔]  │  ← large title header
│                                    │
│ Good morning, Özgür                │  ← greeting (Inter 400, 16px)
│                                    │
│ ┌────────────────────────────────┐ │
│ │ ● MAIL               Active › │ │  ← module card
│ │ 12 unread    ○ 3 drafts       │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ ● OPS                Active › │ │
│ │ 4 orders pending  ○ 2 overdue │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ ● HUB               Syncing › │ │
│ │ 3 runs today ○ 1 failed       │ │
│ └────────────────────────────────┘ │
│                                    │
│ Activity                           │  ← section header
│ ┌────────────────────────────────┐ │
│ │ [feed items...]                │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

- **Single column** layout — module cards stack vertically
- **Greeting:** personalized, Inter 400, 16px, `--text-body`. Time-aware: "Good morning" / "Good afternoon" / "Good evening"
- **Module cards:** only show modules with pending attention (unread, overdue, failed). Quiet modules are collapsed into a "X modules — all clear" summary row at the bottom
- **Activity section:** below module cards, uses the inherited list item anatomy with module attribution (see § Activity Feed)

### Module Card Rules

- **MC1:** Module cards on the home screen show only modules with actionable status. Never show 12 cards — operators see what needs attention.
- **MC2:** KPI values use JetBrains Mono for numeric alignment. Never Inter for numbers in module cards.
- **MC3:** Status pills follow the semantic color system: Active = `--color-success`, Syncing = `--color-info`, Error = `--color-danger`, Inactive = `--text-muted`.
- **MC4:** Tapping a module card navigates to the module root AND sets the bottom tab bar to that module's tabs.

---

## 4. Activity Feed (Mobile)

Adaptation of the web Activity Feed for mobile. Module attribution is mandatory — every entry names the module that produced the event.

### Structure

Uses the inherited list item anatomy (two-line, 64px) with these specifics:

- **Leading:** module icon (20px, monochrome, `--text-muted`)
- **Title line 1:** module label (Inter 500, uppercase, 10px, letter-spacing 1.5px, layer color) + event description (Inter 400, 14px, `--text-body`)
- **Title line 2:** detail text (Inter 400, 13px, `--text-muted`)
- **Trailing:** relative timestamp (Inter 400, 12px, `--text-muted`)

### Examples

```
[mail-icon]  MAIL · New message from Kandil Glass
             Re: Q3 Pricing Proposal                      2m ago

[hub-icon]   HUB · Workflow completed
             Weekly commission calculation — 142 records   15m ago

[ops-icon]   OPS · Order overdue
             Atlas Trading — PO #1042 shipment delayed     1h ago
```

### Activity Feed Rules

- **AF1:** Every activity entry MUST name the source module. "Workflow completed" alone is forbidden — "Tojlo HUB: Workflow completed" is required (inherited from Tojlo T19).
- **AF2:** Module label uses the layer color (Core = accent, Intelligence = purple, Growth = secondary) — not `--text-muted`.
- **AF3:** Activity feed is the "catch-all" surface. If a notification was missed, the activity feed has it. It is the permanent record.
- **AF4:** Tapping an activity entry navigates to the relevant record in the relevant module.

---

## 5. Embedded Module Frame (Mobile)

When Tojlo embeds a third-party module (ERPNext for OPS, n8n for HUB, Wati for CHAT), the mobile app wraps it in a WebView with a Tojlo chrome header.

### Structure

```
┌────────────────────────────────────┐
│ ← OPS                   [⋮] [×]   │  ← Tojlo chrome header (44px)
├────────────────────────────────────┤
│                                    │
│  [WebView: ERPNext content]        │  ← full-bleed WebView
│                                    │
│                                    │
└────────────────────────────────────┘
```

- **Chrome header:** 44px, `--surface-1` background, 1px `--border` bottom
  - Left: back arrow + module name (Inter 500, uppercase, 11px)
  - Right: overflow (⋮) → action sheet (Refresh, Open in browser, Report issue) + close (×)
- **WebView:** full-bleed, no padding. Renders the vendor's mobile-responsive web UI
- **Loading:** show skeleton shimmer in the WebView area while loading. Never a blank white/black screen
- **Error:** if WebView fails to load, show the standard error state (icon + "Failed to load [MODULE]" + "Retry" button) instead of the WebView

### Embedded Frame Rules

- **EF1:** The Tojlo chrome header is always visible above the WebView. The vendor's own navigation bar must be hidden via CSS injection or URL parameters where the vendor allows it (inherited from Tojlo T5).
- **EF2:** Back button in the chrome header navigates within the WebView history first. Only when WebView history is exhausted does it pop the native stack screen.
- **EF3:** Pull-to-refresh on the WebView reloads the embedded content. Standard pull-to-refresh indicator.
- **EF4:** Deep links into embedded modules open the WebView at the correct URL path. Never show the module root and make the user navigate.
- **EF5:** Status bar text in the chrome header reflects connection state: "Connected" (hidden, default), "Syncing..." (shown, `--color-info`), "Offline" (shown, `--color-danger`).

---

## 6. Operator Quick Actions (Mobile)

A floating action button (FAB) for the most common operator actions, scoped to the active module.

### Structure

```
                              ┌─────┐
                              │  +  │  ← FAB, 56px circle
                              └─────┘
                         16px from bottom, 16px from right
```

- **Size:** 56px circle
- **Background:** `--color-accent`
- **Icon:** Lucide Plus, 24px, white
- **Shadow:** `0 4px 12px rgba(0,0,0,0.3)` — one of the few places shadow is used (FABs need elevation to separate from content)
- **Position:** fixed, 16px from right edge, 16px above bottom tab bar

### Behavior

- **Single tap:** if the module has one primary creation action (MAIL → "Compose", CHAT → "New conversation"), execute it directly — navigate to the creation screen.
- **Single tap (multi-action module):** if the module has 2-3 creation actions, open an **action sheet** with options. Example: OPS → "New order" / "New product" / "New supplier".
- **Long press:** always opens the action sheet with all available quick actions for the active module.

### Per-Module Quick Actions

| Module | Primary action (single tap) | Secondary actions (action sheet) |
|---|---|---|
| **OPS** | New order | New product, New supplier |
| **HUB** | Run workflow | New workflow, New trigger |
| **CHAT** | New conversation | New template |
| **MAIL** | Compose | — |
| **VAULT** | Upload document | New folder |
| **TI** | New report | New alert |
| **REACH** | New prospect | New sequence |
| **OUTREACH** | New campaign | New template |

### FAB Rules

- **FAB1:** FAB is visible only on module root screens and list screens. Hide on detail screens, forms, and settings.
- **FAB2:** FAB hides on scroll-down (content is more important), shows on scroll-up or scroll-stop.
- **FAB3:** FAB must not overlap the bottom tab bar. Position it 16px above the tab bar's top edge.
- **FAB4:** If the user lacks permission to create records in the active module, hide the FAB entirely — don't show a disabled button.

---

## 7. Tojlo Onboarding (Mobile Override)

Extends `ocoron-mobile-design-system.md` § Swipeable Onboarding with Tojlo-specific content and a module setup step.

### Pages (5 total)

1. **Welcome** — Tojlo wordmark + "The B2B Operating System" tagline. No illustration needed — the wordmark is the visual.
2. **Value prop 1** — "Twelve modules. One login." + brief description of the unified platform.
3. **Value prop 2** — "AI in every workflow." + brief description of Tojlo TI.
4. **Module selection** — "Which modules do you use?" Grid of 12 module icons with checkboxes. Pre-select the modules provisioned for this tenant. This is informational (personalization), not gating — all provisioned modules are accessible regardless.
5. **Get started** — "Your workspace is ready." + "Open Dashboard" CTA button.

### Onboarding Overrides

- Page 1 uses the Tojlo wordmark (SVG asset, not text font) centered at 80px width
- Page 4 (module selection) uses the module switcher grid layout (3 columns, 80px cells) but with checkboxes
- Final CTA reads "Open Dashboard" (not "Get started") — domain-specific
- Footer on every page: "Tojlo, by Ocoron" in Inter 400, 12px, `--text-muted`
- All inherited ON1-ON6 rules apply (skippable, max 5 pages, no auto-advance)

---

## 8. Push Notification Grouping

Tojlo groups push notifications by module to prevent notification fatigue from 12 modules.

### Grouping Rules

- **Thread ID:** each module gets a unique notification thread/group ID. OS groups notifications per module.
- **Summary:** when 3+ notifications from the same module are pending, collapse into a summary: "Tojlo MAIL — 5 new messages"
- **Icon:** Tojlo monogram (T mark) for all push notifications. Module name in the notification title provides context.
- **Title format:** "Tojlo [MODULE]: [event summary]" — e.g., "Tojlo OPS: New order received"
- **Body:** one-line detail. Deep link payload routes to the relevant record.

### Push Rules

- **PN1:** Never send push notifications from more than 3 modules within a 1-minute window. Queue and stagger. Operators will disable notifications entirely if they feel bombarded.
- **PN2:** Module-level notification preferences: operators can mute individual modules in Settings → Notifications. Muting a module suppresses push but keeps in-app activity feed entries.
- **PN3:** "Quiet hours" setting: suppress all push notifications during configured hours (default: 22:00-08:00 user-local). Critical alerts (system down, payment failed) bypass quiet hours.
- **PN4:** Push notification title always includes the module name (inherited from Tojlo T19). "[MODULE]: [event]" — never just "[event]".

---

## Scaffold Adaptation Note

This file extends `ocoron-mobile-design-system.md` for the Tojlo product specifically. The inheritance chain is:

```
ocoron-design-system.md (tokens)
  └── tojlo-design-system.md (brand + module overrides)
  └── ocoron-mobile-design-system.md (generic mobile patterns)
        └── tojlo-mobile-design-system.md (this file — Tojlo mobile specifics)
```

---

## Rules Summary (Quick Reference)

All Ocoron mobile rules (LI1-LI6, BS1-BS5, AS1-AS5, SR1-SR5, NH1-NH4, ON1-ON6, MF1-MF6) are inherited. Tojlo adds:

| ID | Rule |
|---|---|
| MS1 | Module switcher is always a bottom sheet, never a page |
| MS2 | Module order follows canonical list — never reorder |
| MS3 | Module icons monochrome; color on layer dot only |
| MS4 | Module selection sets bottom tab bar context |
| TB1 | Max 5 tabs (Modules + 3 module tabs + More) |
| TB2 | Tab labels always visible — no icon-only tabs |
| TB3 | Modules tab badge shows pending attention count |
| TB4 | Module switch updates tabs immediately |
| MC1 | Home shows only modules with actionable status |
| MC2 | KPI values use JetBrains Mono |
| MC3 | Status pills follow semantic color system |
| MC4 | Module card tap navigates + sets tab bar |
| AF1 | Every activity entry names the source module |
| AF2 | Module label uses layer color |
| AF3 | Activity feed is the permanent record |
| AF4 | Activity tap navigates to relevant record |
| EF1 | Tojlo chrome header always visible above WebView |
| EF2 | Back navigates WebView history first, then native stack |
| EF3 | Pull-to-refresh reloads embedded content |
| EF4 | Deep links open correct WebView URL path |
| EF5 | Status bar reflects connection state |
| FAB1 | FAB on root/list screens only |
| FAB2 | FAB hides on scroll-down, shows on scroll-up |
| FAB3 | FAB above tab bar, never overlapping |
| FAB4 | Hide FAB if user lacks create permission |
| PN1 | Max 3 modules pushing within 1 minute |
| PN2 | Per-module mute in notification settings |
| PN3 | Quiet hours with critical alert bypass |
| PN4 | Push title always includes module name |
