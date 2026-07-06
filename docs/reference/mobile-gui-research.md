# Mobile (React Native / Expo) GUI toolchain — full research

**Status:** Research reference (the *findings*; the *ruling* lives in `.windsurf/rules/mobile-app/80-mobile.md` — the authority — and the summary in `docs/reference/gui-toolchain.md` § React Native).
**Live-verified:** 2026-07-06 (every claim carries a source URL below; nothing from training memory).
**Scope:** tools for an autonomous Claude Code agent to **build AND verify** RN/Expo mobile GUIs — the mobile analogue of the web stack (Playwright MCP + shadcn MCP + axe). Foundation (unistyles/NativeWind, Ocoron tokens) was already decided in `80-mobile.md`; this focused on the **verification gaps**.

> **Where this doc and `80-mobile.md` ever differ, the pack wins.** `80-mobile.md` already mandated Maestro (E2E), `@testing-library/react-native`, and Mobile Next MCP; this research confirmed those and added two things: Maestro now ships its **own MCP**, and `eslint-plugin-react-native-a11y` as a static a11y lint.

---

## 1. Mobile automation MCP (the RN analogue of Playwright MCP)

**mobile-next / mobile-mcp** — the strongest general-purpose, most-maintained free option (this is `80-mobile.md`'s "Mobile Next MCP").
- Drives native iOS/Android on simulators, emulators, and real devices through a platform-agnostic interface. Tools: `mobile_list_elements_on_screen` (structured a11y tree + coordinates), `mobile_click_on_screen_at_coordinates`, `mobile_type_keys`, `mobile_swipe_on_screen`, `mobile_take_screenshot`/`mobile_save_screenshot`, `mobile_press_button`, `mobile_open_url`. Prefers the native accessibility tree, falls back to screenshot-coordinate taps when labels are missing — "no computer vision model required in Accessibility (Snapshot)."
- Maturity 2026: ~5.4k★, Apache-2.0, active — v0.0.59 (2026-06-09). Free/OSS, local via `npx`; can also run as SSE/HTTP: `npx @mobilenext/mobile-mcp@latest --listen 0.0.0.0:3000` (optional bearer auth) for Docker/networked device hosts.
- Deps: **no Appium.** iOS = native a11y + WebDriverAgent (Xcode CLI → macOS); Android = adb + UI Automator (Android platform-tools). Headless CI: yes (start the emulator/simulator in the background first).
- Install: `claude mcp add mobile-mcp -- npx -y @mobilenext/mobile-mcp@latest`.
- Sources: https://github.com/mobile-next/mobile-mcp · https://mobilenext.ai/docs/mobile-mcp/tools-reference (2026-07-06)

**Competitors (weaker):**
- **appium/appium-mcp** — official Appium MCP (start_session/find_element/click/send_keys/get_page_source). Real, but drags in the full Appium server + UiAutomator2/XCUITest stack — heavier, slower. Only if already on WebDriver. https://github.com/appium/appium-mcp (2026-07-06)
- **infiniV/Android-Ui-MCP** — Android-only, "real-time visual access to your running application." Narrower, smaller. https://github.com/infiniV/Android-Ui-MCP (2026-07-06)
- **jodaco/android-uiautomator-mcp** — Android-only, Python/FastMCP, uiautomator2, 23 tools, stdio+SSE (Docker-friendly), snapshot cache for element-ID stability. Clean Android-only alternative, not cross-platform. https://github.com/jodaco/android-uiautomator-mcp (2026-07-06)
- **sandraschi/uitars-mcp** — NOT mobile. VLM desktop+browser GUI agent, 1★, no iOS/Android. **Disregard for RN.** https://github.com/sandraschi/uitars-mcp (2026-07-06)
- **Expo MCP** — no first-party "drive the app" MCP; the RN-adjacent `ohah/react-native-mcp` has an `accessibility_audit` tool (see §3), not general driving. https://ohah.github.io/react-native-mcp/mcp/tools/accessibility (2026-07-06)

## 2. E2E + flow testing — Maestro vs Detox

**Maestro is the 2026 favorite for RN** (and `80-mobile.md`'s choice), now with both an MCP and a clean CLI + built-in screenshots.
- Maestro: YAML declarative flows, black-box (vision + a11y layer), standalone CLI — no native modules/pods/dev-deps in the project; auto-retries assertions (absorbs flakiness); iOS/Android/RN/Flutter/Web; ~10.5k★; free OSS + optional paid Maestro Cloud. Emits JUnit/HTML reports + artifacts (screenshots/videos/logs). Multiple 2026 teams migrated off Detox → Maestro for lower setup + simpler CI.
- Detox: gray-box, RN-only, syncs to the RN JS thread (<2% flakiness), tests in JS/TS, ~4k★, free. Downsides: native build changes + boilerplate, iOS **simulators only (no iOS real devices)**, iOS requires macOS. Fastest raw execution, heaviest setup.
- **Agent fit — Maestro's first-party MCP** (bundled in the CLI): `claude mcp add maestro -- maestro mcp`. MCP tools: `list_devices`, `inspect_screen` (view hierarchy JSON), `take_screenshot`, `run` (execute inline/file/dir YAML with syntax validation), `cheat_sheet`. Maps onto "run the frozen flow → screenshot → assert." Only the Cloud tools (`run_on_cloud`) are paid.
- Sources: https://docs.maestro.dev/get-started/maestro-mcp · https://www.pkgpulse.com/guides/detox-vs-maestro-vs-appium-react-native-e2e-testing-2026 · https://codersera.com/blog/maestro-vs-appium-vs-detox-2026/ · https://addjam.com/blog/2026-02-18/our-experience-adding-e2e-testing-react-native-maestro/ · https://www.getpanto.ai/blog/detox-vs-maestro (2026-07-06)

## 3. Accessibility for RN — CI gate

No DOM, so axe-core doesn't apply; the 2026 stack is three layers (all enforcing `80-mobile.md` § Accessibility: 44×44/48×48 targets, `accessibilityLabel`, `accessibilityRole`):
- **Static (CI gate):** `eslint-plugin-react-native-a11y` (Formidable) — RN rules: has-accessibility-hint, has-valid-accessibility-role/traits, no-nested-touchables, has-valid-accessibility-descriptors, etc. Plain ESLint, free, zero device. **The axe-equivalent gate for RN.** https://github.com/FormidableLabs/eslint-plugin-react-native-a11y (2026-07-06)
- **Unit/component (CI gate):** `@testing-library/react-native` (RNTL) Jest matchers — `toHaveAccessibleName`, `toHaveAccessibilityValue`, `toBeEnabled/Disabled`, `toBeChecked`, `toBeExpanded`, role/label queries, `isHiddenFromAccessibility`. Actively developed (accessible-name compute updated 2026-02). Free. http://oss.callstack.com/react-native-testing-library/docs/api/jest-matchers.md (2026-07-06)
- **Runtime audit (optional, new 2026):** `react-native-mcp`'s `accessibility_audit` MCP tool (traverses the React Fiber tree, returns severity-tagged violations — call per screen, re-run after fixes) or `react-native-a11y-highlighter` (DEV-only visual overlay, Expo-compatible). `@stark-lab-inc/stark-accessibility-react-native` exists but **needs a Stark SaaS token — paid, flag.** https://ohah.github.io/react-native-mcp/mcp/tools/accessibility · https://github.com/gardouhkhalil-afk/react-native-a11y-highlighter (2026-07-06)
- **Recommendation:** ESLint plugin (fails the lint job) + RNTL matchers (unit tests). Both free + **headless (no simulator)**. Add the runtime audit for deeper per-screen checks when a device is already up.

## 4. Visual regression for RN — self-hostable path

- **Maestro built-in (recommended, new 2026):** `assertScreenshot` (merged PR #2949, supersedes `assertVisual`): `assertScreenshot: { path: screen.png, cropOn: <id>, thresholdPercentage: 95.3 }`; diff image on failure. Capture baselines with `takeScreenshot`, rename to `assertScreenshot`, commit. Self-hosted, free. https://maestro.dev/blog/visual-testing · https://github.com/mobile-dev-inc/Maestro/pull/2949 (2026-07-06)
- **jest-image-snapshot** (American Express) — Jest matcher over pixelmatch, `toMatchImageSnapshot()`, free. Pair with Detox `device.takeScreenshot()` or Maestro screenshots. https://github.com/americanexpress/jest-image-snapshot (2026-07-06)
- **Storybook-driven:** `dannyhw/rn-storybook-test` captures all stories via Maestro, diffs vs baselines, HTML reports, `--update-baseline`, ignore-regions for status-bar noise. Free. https://github.com/dannyhw/rn-storybook-test (2026-07-06)
- **Paid (flag):** Chromatic-style hosted diffing. The self-hostable path above avoids it entirely.

## 5. Foundation status (2026)

- **react-native-unistyles v3** — current (npm 3.2.5; GH v3.2.2, 2026-04-04). Requires New Architecture (Fabric), RN ≥ 0.78, `react-native-nitro-modules` (C++, no re-renders). Expo SDK 54+ auto edge-to-edge. https://github.com/jpudysz/react-native-unistyles (2026-07-06)
- **NativeWind v4.1 stable, v5 preview** — ~7.9k★, ~517K weekly dl (market leader). v5 replaces `cssInterop`/`remapProps` with a `styled` API, shadows → `boxShadow`; stable "sometime in 2026." Scaffold `npx rn-new@latest --nativewind`. https://github.com/nativewind/nativewind (2026-07-06)
- **Tamagui** — CSS-in-JS + compiler + a full pre-built UI kit (unlike unistyles/NativeWind which are styling-only), ~75K weekly dl, RN 0.72+. https://reactnativerelay.com/article/react-native-styling-2026-nativewind-unistyles-tamagui-compared (2026-07-06)
- **React Native Reusables (shadcn-for-RN)** — the closest thing to a shadcn-MCP-equivalent, but **CLI-based, not MCP**: `npx @react-native-reusables/cli@latest init` / `… add <component>`. Built on NativeWind v4, universal shadcn/ui for RN, MIT, copy-in components. **No dedicated MCP exists** — the agent calls the CLI directly (fine for a CLI-agent loop). https://reactnativereusables.com/ (2026-07-06)

---

## Recommended mobile verify stack (mostly free, Linux/Docker-friendly)

- **Drive + screenshot the running app:** **Maestro MCP** (`claude mcp add maestro -- maestro mcp`) — unifies drive/flow/screenshot/regression; the same Maestro `80-mobile.md` mandates for E2E. Add **Mobile Next MCP** (`claude mcp add mobile-mcp -- npx -y @mobilenext/mobile-mcp@latest`) for finer element-level interaction.
- **E2E flows + visual regression:** Maestro YAML flows with `assertScreenshot`. Keep Detox only for gray-box JS-thread-synced RN-only suites.
- **A11y gate:** `eslint-plugin-react-native-a11y` + `@testing-library/react-native` matchers — free, **headless (no device)**, runs in any Linux CI. Optional runtime `accessibility_audit` when a device is up.
- **Skip:** `uitars-mcp` (desktop/browser only), Appium MCP (heavier — only when Maestro/Mobile-Next can't cover a case), Chromatic (paid).

## CI platform reality (Linux/Docker vs macOS)

- **Android emulator = Linux/Docker OK** — headless on `ubuntu-latest` with KVM (`swiftshader_indirect`, `-no-window`); use `reactivecircus/android-emulator-runner`, `arch: x86_64`, `chmod 666 /dev/kvm`. Larger Linux runners give HW-accelerated Android virtualization, 2–3× faster/cheaper than macOS. https://github.com/ReactiveCircus/android-emulator-runner (2026-07-06)
- **iOS simulator = macOS-only** — needs Xcode/WebDriverAgent (Mobile Next MCP) or XCUITest (Detox); Detox iOS is **simulators only, no iOS real devices**. None of this runs in Linux/Docker.
- **Practical gating:** gate on the **Android emulator** (Maestro flows + `assertScreenshot` + Mobile Next MCP driving); run the **a11y layer (ESLint + RNTL) fully headless, no device**; treat **iOS as a macOS-only job** (local Mac or macOS CI runner) when needed.

---

*Sources accessed 2026-07-06. This is the research record; the binding rules are `mobile-app/80-mobile.md`, and the cross-surface decision summary is `docs/reference/gui-toolchain.md`.*
