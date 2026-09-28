"""A new saas-skeleton works as emitted: auth reachable and CSRF-guarded, i18n mounted, no
theme flash, sign-in lands in the app, billing through the portal (mails 01M37NN5, 01M37P3K,
01M37PRR)."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types

import pytest

import fabrik.scaffold as scaffold


@pytest.fixture(scope="module")
def emitted(tmp_path_factory):
    base = tmp_path_factory.mktemp("saasweb")
    out = {}
    for project_type in ("saas-skeleton", "static-site", "office-extension"):
        name = f"p-{project_type.split('-')[0]}"
        scaffold.create_project(
            name=name, description="d", base=base, project_type=project_type, generate_spec=False
        )
        out[project_type] = base / name
    return out


def test_the_idp_web_mode_has_its_csrf_guard_inside_cors(emitted):
    project = emitted["saas-skeleton"]
    main = next(project.glob("server/src/*/main.py")).read_text()
    install = (
        'app.add_middleware(CsrfOriginMiddleware, settings=get_settings(), auth_prefix="/auth")'
    )
    assert install in main
    assert "from fastapi_user_auth import CsrfOriginMiddleware" in main
    # added before CORS, so CORS stays outermost and answers preflights first
    assert main.index(install) < main.index("CORSMiddleware,")
    assert "app.include_router(build_saas_auth_router())" in main


def test_auth_urls_on_the_app_host_reach_the_backend(emitted):
    import yaml

    compose = yaml.safe_load((emitted["saas-skeleton"] / "compose.yaml").read_text())
    rules = [
        label.split("=", 1)[1]
        for label in compose["services"]["api"]["labels"]
        if label.startswith("traefik.http.routers.") and label.split("=", 1)[0].endswith(".rule")
    ]
    assert len(rules) == 1, rules
    assert rules[0].endswith("&& (PathPrefix(`/api`) || PathPrefix(`/auth`))"), rules[0]


def test_the_root_layout_mounts_the_i18n_provider(emitted):
    layout = (emitted["saas-skeleton"] / "app" / "layout.tsx").read_text()
    assert "export default async function RootLayout(" in layout
    assert "const lang = await detectLanguage();" in layout
    assert "<html lang={lang}" in layout
    assert "<I18nProvider lang={lang} strings={strings} fallback={fallback}" in layout
    assert (
        layout.index("<I18nProvider") < layout.index("{children}") < layout.index("</I18nProvider>")
    )


@pytest.mark.parametrize("project_type", ["static-site", "office-extension"])
def test_a_type_without_the_react_kit_gets_no_provider(emitted, project_type):
    project = emitted[project_type]
    layout = (project / "app" / "layout.tsx").read_text()
    assert "@/lib/i18n" not in layout
    assert not (project / "lib" / "i18n" / "I18nProvider.tsx").exists()


@pytest.mark.parametrize("project_type", ["saas-skeleton", "static-site", "office-extension"])
def test_the_theme_is_applied_before_first_paint(emitted, project_type):
    layout = (emitted[project_type] / "app" / "layout.tsx").read_text()
    assert "<script dangerouslySetInnerHTML={{ __html: themeScript }} />" in layout
    assert "prefers-color-scheme: dark" in layout
    assert "suppressHydrationWarning" in layout


def test_a_web_sign_in_lands_in_the_app(emitted):
    env = (emitted["saas-skeleton"] / ".env.example").read_text()
    assert "\nAUTH_WEB_LOGIN_REDIRECT=/app\n" in env


def test_billing_goes_through_the_portal_not_an_in_app_upgrade(emitted):
    page = (
        emitted["saas-skeleton"] / "app" / "(app)" / "app" / "settings" / "page.tsx"
    ).read_text()
    assert "Upgrade to Pro" not in page
    # no route backs a portal session yet, so the control is disabled rather than a dead link
    assert "/api/billing/portal" not in page
    assert "Manage billing" in page and "disabled" in page


def test_a_layout_the_provider_patch_cannot_anchor_fails_loudly(tmp_path):
    layout = tmp_path / "layout.tsx"
    layout.write_text("export default function RootLayout() { return null }\n")
    with pytest.raises(RuntimeError, match="anchor not found"):
        scaffold._wire_i18n_provider(layout)


def test_the_hub_ships_one_i18n_kit():
    kits = sorted(
        p.parent.parent for p in scaffold.FABRIK_ROOT.glob("templates/**/validate_i18n.py")
    )
    assert kits == [scaffold.I18N_KIT_DIR]


def test_the_provider_patch_matches_children_only_at_the_expected_indent(tmp_path):
    """A layout whose children sit deeper must fail loudly, not be half-rewritten."""
    template = (scaffold.FABRIK_ROOT / "templates/saas-skeleton/app/layout.tsx").read_text()
    layout = tmp_path / "layout.tsx"
    layout.write_text(template.replace("        {children}", "          {children}"))
    with pytest.raises(RuntimeError, match="children"):
        scaffold._wire_i18n_provider(layout)


def _load_vendored_idp(project):
    """Load the emitted project's own fastapi_user_auth settings + csrf modules (the package
    __init__ needs argon2, which the hub venv does not carry)."""
    root = next(project.glob("server/src/fastapi_user_auth"))
    pkg = types.ModuleType("fua_probe")
    pkg.__path__ = [str(root)]
    sys.modules["fua_probe"] = pkg
    mods = {}
    for name in ("cookies", "settings", "csrf"):
        spec = importlib.util.spec_from_file_location(f"fua_probe.{name}", root / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods


def _web_origins(project, env):
    tree = ast.parse(next(project.glob("server/src/*/auth.py")).read_text())
    keep = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in {"web_origins", "cors_origins"}
    ]
    assert len(keep) == 2
    ns = {"os": os}
    old = dict(os.environ)
    os.environ.update(env)
    try:
        exec(compile(ast.Module(body=keep, type_ignores=[]), "auth", "exec"), ns)
        return ns["web_origins"]()
    finally:
        os.environ.clear()
        os.environ.update(old)


@pytest.mark.parametrize(
    ("env", "origin", "allowed"),
    [
        ({"NEXT_PUBLIC_APP_URL": "https://app.example.com"}, "https://app.example.com", True),
        ({"NEXT_PUBLIC_APP_URL": "https://app.example.com"}, "https://evil.example", False),
        ({}, "https://app.example.com", False),
        ({"AUTH_ALLOWED_ORIGINS": "https://a.example"}, "https://a.example", True),
    ],
    ids=["own-origin", "foreign-origin", "nothing-configured", "explicit-list"],
)
def test_a_web_login_passes_the_csrf_guard_only_from_an_allowed_origin(
    emitted, env, origin, allowed
):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    project = emitted["saas-skeleton"]
    idp = _load_vendored_idp(project)
    settings = idp["settings"].Settings(
        database_url="postgresql://u:p@db/x",
        jwt_secret="s" * 40,
        allowed_origins=_web_origins(project, env),
    )

    async def login(_request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/auth/login/web", login, methods=["POST"])])
    app.add_middleware(idp["csrf"].CsrfOriginMiddleware, settings=settings, auth_prefix="/auth")
    status = TestClient(app).post("/auth/login/web", headers={"origin": origin}).status_code
    assert (status == 200) is allowed, status


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("stored", "os_dark", "storage_throws", "dark"),
    [
        ("dark", False, False, True),
        ("light", True, False, False),
        (None, True, False, True),
        (None, True, True, True),
    ],
    ids=["stored-dark", "stored-light-beats-os", "os-preference", "storage-blocked"],
)
def test_the_theme_script_picks_the_right_theme(emitted, stored, os_dark, storage_throws, dark):
    layout = (emitted["saas-skeleton"] / "app" / "layout.tsx").read_text()
    script = layout.split("const themeScript = `", 1)[1].split("`;", 1)[0]
    harness = f"""
const cls = new Set();
globalThis.document = {{documentElement: {{classList: {{toggle: (c, on) => on ? cls.add(c) : cls.delete(c)}}}}}};
globalThis.localStorage = {{getItem: () => {{ if ({json.dumps(storage_throws)}) throw new Error("blocked"); return {json.dumps(stored)}; }}}};
globalThis.window = {{matchMedia: () => ({{matches: {json.dumps(os_dark)}}})}};
{script}
process.stdout.write(String(cls.has("dark")));
"""
    out = subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True).stdout
    assert out == str(dark).lower()
