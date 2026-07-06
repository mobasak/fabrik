# GUI Toolchain — the standing decision for building high-quality GUIs with Claude Code

**Status:** Reference / decision doc · **Researched + live-verified:** 2026-07-06 (chrome-ext addendum 2026-07-07) · **Scope:** web (Next.js/React) + React Native + Chrome extension (MV3) — all three surfaces specified (see § React Native / mobile stack and § Chrome extension).

The question this answers: *what MCP / skill / tool / library can we integrate into Claude Code so an agent reliably ships professional GUIs?* The answer is not one tool — it is a **four-layer stack**, almost entirely free and self-hostable. The single highest-leverage piece is the **visual feedback loop**: an agent that opens its own running UI, screenshots it, reads the accessibility tree, and self-verifies. Without it an agent builds blind; with it, GUI quality becomes *checkable* instead of hopeful.

This composes with — it does not replace — our existing design systems (`ocoron-design-system.md` / `tojlo-design-system.md`), `saas/60-saas-ui.md`, and the `/fabrik-ui-design` + `/fabrik-data-contract` contracts.

---

## The four layers (+ the design-thinking layer that sits above them)

```
DESIGN-THINK   frontend-design skill (anti-slop: token system + signature element + self-critique)
     │
     ▼
1. FOUNDATION  shadcn/ui + Tailwind v4 + Base UI  ·  shadcn MCP (install real components)  ·  tweakcn (tokens)
2. GENERATE    Superdesign (interactive, free)  ·  [paid] v0 API / 21st Magic MCP
3. SEE&VERIFY  Playwright MCP (agent drives + screenshots its own UI)  ·  Chrome DevTools MCP (debug)  ·  local Ollama VLM (judge "is it good")
4. GATE (CI)   @axe-core/playwright + Playwright toHaveScreenshot + better-tailwindcss token-lint + Lighthouse CI
     │
     ▼
REVIEW         OneRedOak design-review (critique the RENDERED UI) + Vercel web-design-guidelines (static a11y/UX audit)
```

---

## Recommended stack (verified)

| Tool | Layer | Role | Cost / self-host | Install / invoke (verified 2026-07-06) |
|---|---|---|---|---|
| **frontend-design** skill | design-think | Forces a token system + one "signature" element + a self-critique before any CSS; names the AI-slop clusters to avoid. Anthropic's #1 frontend rec: *design before code*. | Free (MIT). **Already installed here.** | Invoke the `frontend-design` skill (present in `anthropic-agent-skills` + `claude-plugins-official` marketplaces). |
| **shadcn/ui** + Tailwind v4 + Base UI | foundation | Copies real component source into the repo (agent edits real code, not an opaque lib). Base UI is shadcn's default primitive (July 2026); Radix still supported. | Free (MIT), self-host registries as static JSON. | `pnpm dlx shadcn@latest init` |
| **shadcn MCP** | foundation | Agent searches + installs vetted components from public/private registries on demand — stops invented markup. | Free, local, official. | `pnpm dlx shadcn@latest mcp init --client claude` (registries in `components.json`) |
| **tweakcn** | foundation | Visual editor that emits the standard shadcn `globals.css` OKLCH token block (our design-system tokens). | Free (Apache-2.0), Docker self-host. | Web app or self-host; output is plain CSS vars. |
| **Playwright MCP** ⭐ | see & verify | **The visual feedback loop.** Agent drives its own running UI, reads the a11y tree (structural truth, no vision model needed), clicks flows, screenshots, self-verifies. Highest-leverage integration. | Free (Apache-2.0), official Microsoft, headless/CI, Docker chromium-only, **web-only**. | `claude mcp add playwright npx @playwright/mcp@latest` |
| **Chrome DevTools MCP** | see & verify | The "debug" half — perf traces, console + source maps, network, DOM — for *why* it looks wrong. | Free, official Google. | `claude mcp add chrome-devtools --scope user npx chrome-devtools-mcp@latest` |
| **local Ollama VLM** (InternVL 2.5 8B / MiniCPM-V) | see & verify | Pixel-diff says "did it change"; a local vision model judges "is it *good*" (misalignment, overflow, contrast). Zero API cost. | Free, self-host on VPS. | Ollama + a vision model; call only on changed screenshots. |
| **@axe-core/playwright** | gate | WCAG 2.2 AA rule check on the rendered page; `expect(results.violations).toEqual([])`. Catches ~30–57 % of WCAG (a floor). | Free (MPL/Apache). | `npm i -D @axe-core/playwright` |
| **Playwright `toHaveScreenshot`** | gate | Visual-regression gate; run inside the official Playwright Docker image so render is byte-stable local==CI. Baselines in git (or reg-suit + MinIO). | Free, no SaaS. | built into `@playwright/test`; baseline in the Playwright Docker image |
| **eslint-plugin-better-tailwindcss** *(or oxlint-tailwindcss)* | gate | Bans off-token colors/spacing → mechanically enforces the design system on Tailwind v4. **Do NOT use the classic `eslint-plugin-tailwindcss`** — its v4 support is beta/partial. | Free (MIT). | ESLint flat config, `--max-warnings=0` |
| **eslint-plugin-jsx-a11y** | gate | Static pre-render a11y check on JSX (fastest first line). | Free (MIT). Note: release cadence stalled; ESLint 10 support still an open PR. | ESLint flat config |
| **Lighthouse CI** | gate | Perf + a11y *budget/regression* gate (`minScore`). Self-host the LHCI server, no SaaS. | Free (Apache-2.0). | `@lhci/cli` + `lighthouserc.js` assertions |
| **OneRedOak design-review** | review | Critiques the **rendered** UI (drives Playwright MCP; sub-agents check UX/responsive/a11y; posts PR feedback). The UI analogue to a code review. | Free (MIT). ⚠️ last pushed Sep 2025. | Copy the `design-review/` agents + `/design-review` command into `.claude/`; requires Playwright MCP. |
| **Vercel web-design-guidelines** | review | Static audit of UI code against 100+ a11y/UX rules. | Free. | `npx skills add vercel-labs/agent-skills -a claude-code` → `/web-interface-guidelines` |
| **dataviz** skill | foundation | Design-system-agnostic method for charts/dashboards/stat-tiles. Read before any chart code. | Free, built-in. | Invoke the `dataviz` skill. |
| **Superdesign** | generate | Free open-source **IDE extension** (VS Code/Cursor sidebar + canvas): generate mockups/components/wireframes, extract a design system from a screenshot. **Interactive / human-in-the-loop — NOT a headless MCP the autonomous agent drives.** | Free (OSS), BYO-key or your subscription; designs in `.superdesign/`. | Install the SuperDesign extension from the VS Code/Cursor marketplace; use the sidebar/canvas. |

---

## Paid / avoid-in-the-agent-loop

| Tool | Why flagged |
|---|---|
| **v0 Platform API / v0-sdk** | Agent-callable (REST + OpenAI-compatible + SDK) but **paid SaaS** (~$20/mo, credit-metered, closed model). Use only if you want v0's model quality. |
| **21st.dev Magic MCP** | Generates *novel* components (vs shadcn MCP's install-only) but **freemium metered SaaS**; overlaps the free path. |
| **Figma Dev Mode MCP** | Only if you design in Figma. Free remote server, but **Code Connect (the part that stops component hallucination) needs Org/Enterprise seats**. |
| **Chromatic / Argos** | Visual-regression **cloud SaaS**. Keep out of the agent's pass/fail loop; use free `toHaveScreenshot` + reg-suit instead. |
| **Lost Pixel** | ❌ **Dead** — OSS repo archived April 2026. Do not adopt. |

## React Native / mobile stack (the web loop is browser-only — RN has its own)

The web loop (Playwright MCP / shadcn MCP / Chrome DevTools MCP / axe) **cannot drive a running RN app** — it's Chromium-only. RN has its own stack, and **`.windsurf/rules/mobile-app/80-mobile.md` (§ Testing + § MCP Servers) is the authority — this table is the *toolchain view* of what that pack already mandates** (Maestro E2E in `.maestro/`, `@testing-library/react-native`, **Mobile Next MCP**, plus Expo / iOS-Simulator / Appium MCP), with two additions verified 2026-07-06: Maestro now ships its *own MCP*, and a static a11y lint. Where this doc and `80-mobile.md` ever differ, **the pack wins.** Mostly-free, Linux/Docker-friendly:

| Layer | Tool | Role | Cost / CI | Install |
|---|---|---|---|---|
| foundation (styling) | **`react-native-unistyles` v3** (Ocoron theming) or **NativeWind v4.1** | RN styling with the same Ocoron tokens as web (`mobile-app/80-mobile.md` decides) | free | npm |
| foundation (components) | **React Native Reusables** (shadcn-for-RN) | copy-in universal components; **CLI, not MCP** — the agent calls `npx @react-native-reusables/cli@latest add <c>` | free (MIT) | CLI |
| **see + verify (primary)** ⭐ | **Maestro MCP** | one server = **drive + E2E flows + screenshots + visual regression** (`inspect_screen`, `take_screenshot`, `run`). The RN analogue of Playwright MCP *and* toHaveScreenshot combined. | free/self-host; Cloud tools paid | `claude mcp add maestro -- maestro mcp` (needs the `maestro` CLI) |
| see + verify (exploratory) | **Mobile Next MCP** (`@mobilenext/mobile-mcp`) — the pack's listed a11y-tree driver | free-form element-level driving (a11y-tree list, coordinate taps) when YAML flows are too coarse; Apache-2.0, active | free/self-host | `claude mcp add mobile-mcp -- npx -y @mobilenext/mobile-mcp@latest` |
| visual regression | **Maestro `assertScreenshot`** (built-in) | pixel-diff vs committed baselines, diff image on failure — no extra dep | free | in the Maestro flow |
| **a11y gate (headless — no device)** | **`eslint-plugin-react-native-a11y`** + **`@testing-library/react-native`** matchers | the axe-equivalent for RN (no DOM): static lint + component-test a11y assertions; runs in any Linux CI with **no simulator** | free | npm devDeps |

**Leanest primary for RN: Maestro's MCP** (`claude mcp add maestro -- maestro mcp`) — it unifies drive/flow/screenshot/regression and is the *same Maestro* `80-mobile.md` already mandates for E2E. **Mobile Next MCP** (`@mobilenext/mobile-mcp`) is the finer exploratory add. The pack also lists **Expo MCP** (EAS/SDK, simulator screenshots) and **iOS Simulator MCP** (idb) — use them for their niches, and **Appium MCP** only when Maestro/Mobile-Next can't cover a case. Skip `uitars-mcp` (desktop/browser only) and Chromatic (paid). The one *net-new* addition beyond the pack is **`eslint-plugin-react-native-a11y`** as a static a11y lint alongside the pack's `@testing-library/react-native`.

**CI platform reality:** **Android emulator runs headless on Linux/Docker** (KVM, `reactivecircus/android-emulator-runner`, `-no-window`) — gate mobile there. The **a11y layer (ESLint + RNTL) needs no device at all**. **iOS simulator is macOS-only** (Xcode/WebDriverAgent) — treat iOS verification as a separate macOS job when needed. Prereqs for the MCPs are heavier than the web ones (Android SDK/emulator, or macOS+Xcode, and the `maestro` CLI), so wire them **at mobile-build-time**, not pre-emptively user-global.

---

## Chrome extension (MV3) surface (reuse the web loop + 3 additions)

Extension surfaces (popup / options / side-panel / content-script overlay) are **web tech**, so the agent **reuses the entire web loop above** (frontend-design → shadcn MCP → Playwright MCP → `@axe-core/playwright` + `toHaveScreenshot` → `/design-review`) with the **same Ocoron (Compact) design system** `.windsurf/rules/chrome-ext/70-chrome-ext.md` already mandates. **`70-chrome-ext.md` (§ Testing & UI Verification) is the authority — this is the toolchain view.** MV3 forces exactly three additions (full research: `docs/reference/chrome-ext-gui-research.md`, live-verified 2026-07-07):

| # | Addition | Why (MV3 fact) |
|---|---|---|
| 1 | **Playwright test *fixture* that loads the unpacked build** (`launchPersistentContext('', { channel:'chromium', args:['--disable-extensions-except=…','--load-extension=…'] })`, ID from the service worker, `goto('chrome-extension://<id>/…')`). Pin `@playwright/test` ≥1.59. | **Playwright MCP alone can't load an extension** (drives a running browser); **stable Chrome ≥137 removed `--load-extension`** → must use bundled Chromium / Chrome-for-Testing. |
| 2 | **`bypassCSP: true` on the extension context for axe** + pinned **400px popup viewport** for `toHaveScreenshot`. | Extension CSP is strict + **non-relaxable** → axe throws on `chrome-extension://` pages without it; a `goto`-ed popup otherwise renders at the tab viewport. |
| 3 | **`size-limit` + `@size-limit/preset-app`** per-surface budget gate. | `70-chrome-ext.md` § Bundle Budgets sets the KB numbers but names no *tool* — this is the CI gate for them. |

**Nice-to-have:** Chrome DevTools MCP `--category-extensions` (already user-global) — `install_extension`/`reload_extension`/`trigger_extension_action` + live SW console/perf, pointed at Chrome-for-Testing; interactive debug, not the automated gate. Everything is **free / self-hostable** — skip paid visual-diff SaaS. No bespoke extension MCP is needed: the Playwright fixture is the load+assert backbone, the web gate tools all apply unchanged.

---

## How it maps to the fabrik pipeline

```
/fabrik-spec → /fabrik-data-contract → /fabrik-ui-design (screens+flows, design-system-first)
   → BUILD:   shadcn MCP + `frontend-design` skill  (+ Superdesign interactively / v0 if paid)
   → SEE:     Playwright MCP (agent drives + screenshots its own UI)
   → REVIEW:  OneRedOak design-review + Vercel web-design-guidelines   ← the UI analogue to /fabrik-review
   → GATE:    @axe-core/playwright + toHaveScreenshot + better-tailwindcss token-lint  (CI, red-on-fail)
```

`/fabrik-ui-design` + `/fabrik-data-contract` define **what** to build; this toolchain is **how** the agent builds and proves it. The visual loop + the CI gate turn the ui-design contract's "Done When" from prose into machine-checked reality.

## Integrate-first (biggest bang, ~$0)

1. **`frontend-design` skill** — already installed; make it a standing step in `/fabrik-ui-design` builds.
2. **Playwright MCP** — the agent sees + verifies its own UI. *Transformational.*
3. **shadcn MCP** — stops invented markup.
4. **OneRedOak design-review + `@axe-core/playwright` gate** — makes "good UI" mandatory, mirroring `/fabrik-review`.
5. **Superdesign** (interactive) for generation, or **v0 API** if you'll pay for autonomous generation.

---

*All tools verified against their official source (npm / GitHub / vendor docs) on 2026-07-06. Install commands quoted are the verified current forms. `frontend-design` presence confirmed in the local `anthropic-agent-skills` + `claude-plugins-official` marketplaces.*
