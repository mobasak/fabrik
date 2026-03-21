---
activation: glob
globs: ["**/manifest.json"]
description: Chrome extension UI patterns — MV3, surfaces, state, bundles, accessibility
trigger: glob
---

# Chrome Extension UI Rules

Apply when working on Chrome extension code. Skip for Python, Docker, and infrastructure files.

## MV3 Constraints

- Service workers replace background pages; do not use DOM or `window` APIs in the service worker.
- Service workers terminate on idle; never rely on in-memory globals for durable state.
- Package all executable code with the extension; never load remote executable code at runtime.
- CSP forbids `unsafe-eval` and inline scripts; keep all JavaScript in versioned files.

## UI Surfaces

- Use the popup for a single primary action; it closes on focus loss, so never leave the system in a half-finished state.
- Use the side panel for persistent or multi-step work, and only when the `sidePanel` permission is declared.
- Use the options page for full preferences and advanced configuration; always link to it from the popup.
- Use Shadow DOM isolation for content-script overlays to avoid style collisions with the host page.

## State Management

- Use `chrome.storage` as the cross-context source of truth across service worker, popup, side panel, and content scripts.
- Persist all user-relevant state before the popup closes.
- Add Zustand only for local reactive UI state in React or Preact surfaces.
- Never store durable state in service-worker globals.

## Framework Choice

- Use Preact for minimal popup UIs where bundle size is the primary constraint.
- Use Svelte for medium-complexity extensions spanning popup, options, and content-script overlays.
- Use Shadow DOM with Svelte content-script overlays to isolate extension styles from the page.
- Use React only for complex side-panel or application-like flows, and split code aggressively.
- Use vanilla JavaScript and native Web APIs for the smallest possible scope.

## Bundle Budgets

- Keep popup initial JavaScript in the single-digit to low-tens KB gzip range.
- Keep the side-panel initial entry well below the typical React baseline by splitting route and feature chunks.
- Lazy-load options sections and heavy side-panel panes with dynamic imports.
- Verify bundle budgets by inspecting emitted build artifacts before shipping.

## Build Tooling

- Default to Vite with `@crxjs/vite-plugin` for MV3-aware builds, HMR, and multi-entrypoint support.
- Use WXT or Plasmo only when the project already depends on them or their abstractions are required.
- Configure `build.rollupOptions` manual chunks for multi-entrypoint bundle splitting.
- Never ship production bundles that depend on `eval`-style development transforms.

## Accessibility

- Prefer native `<button>`, `<input>`, and `<select>` controls for built-in keyboard and screen-reader support.
- Keep keyboard focus visible on every surface, including popup, side panel, options, and overlays.
- Make custom widgets follow WAI-ARIA APG keyboard interaction patterns exactly.
- Ensure content-script overlays are keyboard reachable, dismissible, and return focus logically to the page.
- Animate only `transform` and `opacity`, and respect `prefers-reduced-motion`.

## Done When

- [ ] The service worker persists durable state to `chrome.storage` and does not rely on globals.
- [ ] No extension page uses inline JavaScript or `eval`.
- [ ] The popup renders its primary action synchronously.
- [ ] All interactive controls are keyboard accessible and show visible focus.
- [ ] Bundle sizes are checked against popup and side-panel budgets.
- [ ] `_locales/en/messages.json` exists for all user-visible strings.
