"""chrome-extension scaffold emits a WXT (not @crxjs) extension lane.

Structure assertions (fast, no pnpm/build). The end-to-end build gate
(`pnpm install` → `wxt build` → tsc → size-limit → eslint, all exit 0) is the
integration verification run at plan-execution time — see the plan's Evidence.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from fabrik.scaffold import I18N_ENABLED_TYPES, TYPE_REQUIRED_FILES, create_project

FABRIK_ROOT = Path("/opt/fabrik")
# Portability guard (matches tests/test_scaffold.py): these tests scaffold against the
# real templates tree — skip cleanly where it isn't present (e.g. CI) rather than error.
pytestmark = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires the full fabrik environment at /opt/fabrik (templates dir)",
)


@pytest.fixture
def ext(tmp_path: Path) -> Path:
    """Scaffold a chrome-extension and return its extension/ dir."""
    create_project(
        "cxwxttest",
        "WXT chrome-ext test",
        base=tmp_path,
        project_type="chrome-extension",
        generate_spec=False,
    )
    return tmp_path / "cxwxttest" / "extension"


def test_emits_wxt_config_not_vite_or_manifest(ext: Path) -> None:
    """WXT owns the build + auto-generates the manifest — no vite.config/manifest.json."""
    assert (ext / "wxt.config.ts").exists()
    assert not (ext / "vite.config.ts").exists()
    assert not (ext / "manifest.json").exists()  # WXT auto-generates it


def test_wxt_config_wires_preact_compat_and_i18n(ext: Path) -> None:
    """@preact/preset-vite (react→preact/compat) + @wxt-dev/i18n/module."""
    cfg = (ext / "wxt.config.ts").read_text()
    assert "@preact/preset-vite" in cfg
    assert "preact()" in cfg
    assert "@wxt-dev/i18n/module" in cfg  # /module subpath, not the bare package


def test_file_based_entrypoints(ext: Path) -> None:
    """WXT file-based entrypoints under src/."""
    for p in (
        "src/entrypoints/background.ts",
        "src/entrypoints/content.tsx",
        "src/entrypoints/popup/index.html",
        "src/entrypoints/popup/main.tsx",
        "src/entrypoints/options/main.tsx",
        "src/locales/en.json",
    ):
        assert (ext / p).exists(), p


def test_package_json_is_wxt_not_crxjs(ext: Path) -> None:
    """WXT dep set; no @crxjs; webext-permission-toggle pinned to the stable ^6 line."""
    import json

    pkg = json.loads((ext / "package.json").read_text())
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "wxt" in deps
    assert "preact" in deps
    assert "@preact/preset-vite" in deps
    assert not any("crxjs" in d for d in deps), "must not depend on @crxjs"
    assert deps["webext-permission-toggle"].startswith("^6"), "pin the stable v6 line"


def test_pnpm_workspace_allowbuilds_not_onlybuilt(ext: Path) -> None:
    """pnpm 11 uses allowBuilds (onlyBuiltDependencies was removed) so install exits 0."""
    ws = (ext / "pnpm-workspace.yaml").read_text()
    assert "allowBuilds:" in ws
    assert "esbuild: true" in ws
    assert "onlyBuiltDependencies" not in ws


def test_type_required_files_flipped_to_wxt() -> None:
    """The required-files contract no longer lists manifest.json/vite.config.ts."""
    req = TYPE_REQUIRED_FILES["chrome-extension"]
    assert "extension/wxt.config.ts" in req
    assert "extension/manifest.json" not in req
    assert "extension/vite.config.ts" not in req


def test_i18n_owned_by_wxt_dev_i18n() -> None:
    """chrome-extension dropped the legacy chrome_messages.py strategy (@wxt-dev/i18n owns it)."""
    assert "chrome-extension" not in I18N_ENABLED_TYPES


def test_compose_traefik_cors_uses_regex_not_glob(tmp_path: Path) -> None:
    """Traefik's accessControlAllowOriginList is EXACT-match (not glob) and Traefik
    synthesizes the preflight itself (never reaching FastAPI). So `chrome-extension://*`
    never matches a real ID → a deployed extension can't reach its backend. Must use the
    *Regex variant + credentials."""
    create_project(
        "cxcompose", "x", base=tmp_path, project_type="chrome-extension", generate_spec=False
    )
    compose = (tmp_path / "cxcompose" / "compose.yaml").read_text()
    assert "accesscontrolalloworiginlistregex=^chrome-extension://.*$" in compose
    assert "accesscontrolallowcredentials=true" in compose
    # the broken exact-match glob must be gone
    assert "accesscontrolalloworiginlist=chrome-extension://*" not in compose


def test_tailwind_v4_wired(ext: Path) -> None:
    """Tailwind v4 (@tailwindcss/vite) is wired into the build (plan Phase A wxt.config + deps)."""
    import json

    pkg = json.loads((ext / "package.json").read_text())
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "@tailwindcss/vite" in deps
    assert "tailwindcss" in deps
    assert "tailwindcss()" in (ext / "wxt.config.ts").read_text()
    css = (ext / "src" / "global.css").read_text()
    assert css.lstrip().startswith('@import "tailwindcss";')
    # Ocoron design-system tokens are CSS-first (@theme), per chrome-ext/70-chrome-ext.md.
    assert "@theme {" in css
    assert "--color-accent:" in css


def test_wxt_config_declares_mv3_permissions_and_icons(ext: Path) -> None:
    """The manifest permissions + explicit icons are declared (WXT auto-discovery
    won't match our icon16.png names, so they must be wired or Chrome shows no icon)."""
    cfg = (ext / "wxt.config.ts").read_text()
    # contextMenus is required or the background SW throws in onInstalled (GUI-loop finding).
    assert "permissions: ['storage', 'activeTab', 'contextMenus']" in cfg
    assert "icons: {" in cfg
    assert "/icon16.png" in cfg


# ---------------------------------------------------------------------------
# Phase B — Preact Ocoron surfaces + MV3 seams + native snippets (structure).
# The RUNTIME behaviors (compat render, onboarding-on-install, settings round-trip,
# shadow-root overlay, SW-mediated token relay) are the Playwright load-extension
# GUI loop — see the plan's Build Verification Loop; here we assert the seams exist.
# ---------------------------------------------------------------------------


def test_phase_b_lib_seams_present(ext: Path) -> None:
    """The MV3 seams a real Ocoron extension binds to: storage, messaging, sentry,
    api config, consent, and the Ocoron Preact Button."""
    for p in (
        "src/lib/storage.ts",
        "src/lib/messaging.ts",
        "src/lib/sentry.ts",
        "src/lib/consent.ts",
        "src/lib/api/config.ts",
        "src/components/ui/button.tsx",
    ):
        assert (ext / p).exists(), p


def test_phase_b_storage_uses_wxt_dev_storage(ext: Path) -> None:
    """Settings + the token seam go through @wxt-dev/storage's defineItem (typed,
    local vs. session), not raw chrome.storage — token in session (cleared on close)."""
    src = (ext / "src" / "lib" / "storage.ts").read_text()
    assert "defineItem" in src
    assert "session:" in src, "the auth token must live in storage.session"


def test_phase_b_messaging_uses_webext_bridge(ext: Path) -> None:
    """SW-mediated token relay is a typed webext-bridge ProtocolMap (get-token)."""
    src = (ext / "src" / "lib" / "messaging.ts").read_text()
    assert "webext-bridge" in src
    assert "get-token" in src


def test_storage_seam_is_token_pair_plus_pkce(ext: Path) -> None:
    """Storage widened from a single JWT to the {access, refresh} pair + the PKCE slot
    (fabrik-lib auth-kit request) — all session-scoped, never local:."""
    src = (ext / "src" / "lib" / "storage.ts").read_text()
    assert "interface TokenPair" in src
    for fn in ("getTokens", "setTokens", "clearTokens"):
        assert f"export const {fn}" in src, fn
    assert "'session:tokens'" in src, "tokens must be session-scoped (cleared on browser close)"
    assert "'session:auth.pkceVerifier'" in src, "the transient OAuth PKCE slot"
    # getToken() convenience read stays for the 'get-token' message; the raw single-token
    # setter is gone (writes go through setTokens/clearTokens, which keep the pair invariant).
    assert "export const getToken" in src
    assert "export const setToken " not in src


def test_messaging_seam_has_authed_fetch_protocol(ext: Path) -> None:
    """The preferred authed-call path is a typed 'authed-fetch' message — the content
    script hands the SW a request and never receives the token."""
    src = (ext / "src" / "lib" / "messaging.ts").read_text()
    assert "'authed-fetch'" in src
    assert "interface SerializableRequest" in src
    assert "AuthedFetchResult" in src
    assert "interface ProblemDetails" in src


def test_authed_fetch_is_api_origin_only_proxy(ext: Path) -> None:
    """SECURITY INVARIANT (regression guard, from the pool review): authed-fetch REFUSES any
    non-API origin at entry — a compromised content script cannot turn the SW into an open
    proxy / SSRF vector or make it attach the token to an attacker URL. The Bearer is therefore
    only ever attached for the (exact-origin-matched) API."""
    src = (ext / "src" / "lib" / "api" / "authed-fetch.ts").read_text()
    assert "new URL(url).origin === new URL(API_BASE_URL).origin" in src, "exact-origin guard"
    assert "if (!isApiOrigin(req.url))" in src, "entry-gate refuses non-API origins"
    assert "origin_not_allowed" in src
    assert "setRefreshHandler" in src, "the pluggable 401-refresh hook"
    assert "=== 401" in src, "401-refresh-retry-once machinery"
    # The SW is the SOLE authority on Authorization — a caller-supplied header is dropped so an
    # untrusted content script can't forward a forged Bearer when no token is stored.
    assert "headers.delete('Authorization')" in src


def test_authed_fetch_single_flights_refresh(ext: Path) -> None:
    """Regression (pool review): concurrent 401s must share ONE refresh, or a rotating /
    single-use refresh token gets spent twice and logs the user out."""
    src = (ext / "src" / "lib" / "api" / "authed-fetch.ts").read_text()
    assert "refreshInFlight" in src
    assert "refreshOnce" in src


def test_authed_fetch_strips_authorization_from_response(ext: Path) -> None:
    """Regression (pool review): defense-in-depth — an Authorization echo in a response header
    must not be forwarded to the untrusted content script."""
    src = (ext / "src" / "lib" / "api" / "authed-fetch.ts").read_text()
    assert "!== 'authorization'" in src


def test_authed_fetch_rejects_empty_access_refresh(ext: Path) -> None:
    """Regression (confirming pool round): a malformed refresh ({access:''}) must NOT be
    persisted — otherwise storage is corrupted and the user is silently de-authenticated."""
    src = (ext / "src" / "lib" / "api" / "authed-fetch.ts").read_text()
    assert "if (refreshed?.access)" in src, "guard the refresh on a non-empty access token"


def test_authed_fetch_wired_into_background_sw(ext: Path) -> None:
    """The SW answers 'authed-fetch' (the handler that keeps the token off the content script)."""
    bg = (ext / "src" / "entrypoints" / "background.ts").read_text()
    assert "onMessage('authed-fetch'" in bg
    assert "authedFetch" in bg


def test_phase_b_sentry_is_isolated_client(ext: Path) -> None:
    """Content scripts use an isolated BrowserClient + Scope, never a global
    Sentry.init (which would leak into / conflict with the host page)."""
    src = (ext / "src" / "lib" / "sentry.ts").read_text()
    assert "BrowserClient" in src
    assert "Sentry.init" not in src


def test_phase_b_background_registers_onboarding_and_commands(ext: Path) -> None:
    """background.ts: onboarding on install + contextMenus/commands registered INSIDE
    onInstalled (MV3 SW re-runs; top-level registration double-registers)."""
    src = (ext / "src" / "entrypoints" / "background.ts").read_text()
    assert "onInstalled" in src
    assert "onboarding.html" in src
    assert "contextMenus" in src
    assert "commands" in src
    assert "onMessage('get-token'" in src, "SW mediates the token relay"


def test_phase_b_content_uses_shadow_root_ui(ext: Path) -> None:
    """content.tsx mounts via createShadowRootUi (cssInjectionMode:'ui') so host-page
    CSS can't bleed into the overlay; px (shadow DOM has no rem context)."""
    src = (ext / "src" / "entrypoints" / "content.tsx").read_text()
    assert "createShadowRootUi" in src
    assert "cssInjectionMode: 'ui'" in src


def test_phase_b_content_unmounts_preact_on_remove(ext: Path) -> None:
    """Regression (pool-review finding): preact does NOT auto-unmount when WXT tears the
    container down — onRemove must render(null) or the overlay leaks on SPA remounts."""
    src = (ext / "src" / "entrypoints" / "content.tsx").read_text()
    assert "render(null, container)" in src, "onRemove must explicitly unmount the vnode tree"


def test_phase_b_popup_proves_preact_compat(ext: Path) -> None:
    """popup imports a hook from 'react' — proving the preact/compat alias resolves
    (a real React-ecosystem lib would import this way)."""
    src = (ext / "src" / "entrypoints" / "popup" / "main.tsx").read_text()
    assert "from 'react'" in src


def test_phase_b_options_settings_form_over_storage(ext: Path) -> None:
    """options is a settings form bound to the @/lib/storage settings item."""
    src = (ext / "src" / "entrypoints" / "options" / "main.tsx").read_text()
    assert "settings" in src
    assert "@/lib/storage" in src


def test_phase_b_onboarding_asset_present(ext: Path) -> None:
    """The onboarding page background.ts opens on install ships in public/."""
    assert (ext / "public" / "onboarding.html").exists()


def test_phase_b_html_has_lang(ext: Path) -> None:
    """Regression for the GUI-loop axe finding (html-has-lang, serious): the popup +
    options index.html declare lang so the built pages pass @axe-core."""
    for p in ("popup/index.html", "options/index.html"):
        html = (ext / "src" / "entrypoints" / p).read_text()
        assert '<html lang="en">' in html, p
    # onboarding is a full-tab page — it needs lang too.
    assert '<html lang="en">' in (ext / "public" / "onboarding.html").read_text()


def test_phase_b_seams_doc_emitted(ext: Path) -> None:
    """The scaffold documents the seam contracts a future chrome-ext-* kit binds to
    (plan Phase B step 6). SEAMS.md sits in the project's docs/reference/."""
    seams = ext.parent / "docs" / "reference" / "SEAMS.md"
    assert seams.exists()
    body = seams.read_text()
    for seam in ("src/lib/storage.ts", "src/lib/messaging.ts", "get-token", "createIsolatedSentry"):
        assert seam in body, seam


@pytest.mark.skipif(
    shutil.which("pnpm") is None or shutil.which("node") is None,
    reason="requires the node/pnpm toolchain (the build integration gate)",
)
def test_wxt_scaffold_builds_and_manifest_has_permissions(tmp_path: Path) -> None:
    """Behavior Contract (a): a fresh scaffold `pnpm install` + `wxt build` exits 0 and
    the generated manifest carries the declared MV3 permissions. This is the real proof
    the rewrite builds — slow (installs deps), gated on the toolchain being present."""
    import json
    import subprocess

    create_project(
        "cxbuildtest",
        "WXT build test",
        base=tmp_path,
        project_type="chrome-extension",
        generate_spec=False,
    )
    ext = tmp_path / "cxbuildtest" / "extension"
    inst = subprocess.run(["pnpm", "install"], cwd=ext, capture_output=True, text=True, timeout=600)
    assert inst.returncode == 0, f"pnpm install failed:\n{inst.stderr[-2000:]}"
    build = subprocess.run(
        ["npx", "wxt", "build"], cwd=ext, capture_output=True, text=True, timeout=400
    )
    assert build.returncode == 0, f"wxt build failed:\n{build.stderr[-2000:]}"
    manifest = json.loads((ext / ".output" / "chrome-mv3" / "manifest.json").read_text())
    assert manifest["permissions"] == ["storage", "activeTab", "contextMenus"]
    # The custom command seam is registered (not the reserved _execute_action).
    assert "open-settings" in manifest.get("commands", {})
    assert manifest["default_locale"] == "en"
    # Icons wired into the built manifest (else Chrome shows the gray puzzle default).
    assert manifest["icons"] == {"16": "/icon16.png", "48": "/icon48.png", "128": "/icon128.png"}
