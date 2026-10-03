"""Pins the two `desktop-app` packs to the rules their 2026-10-03 currency pass set.

`72-desktop.md` is glob-activated on Electron paths (no fleet project matches today; the scaffold template does) and
`00-domain-desktop-app.md` is loaded by path at vision intake. What they state can go false with no other gate red:

1. Both carry `currency_pass:`; 00 names the planner commands that load it, and they do load it by path.
2. 00's ONE RULE — no dollar amount and no percentage — and every `72-desktop.md § <section>` it cites exists.
3. 72's version policy is the supported-major window, never a version floor.
4. The renderer lockdown: the three webPreferences, permissions, navigation, new windows, IPC sender origin, fuses.
5. Storage: a raw random key for SQLCipher, the KDF facts stated right, `safeStorage`'s `basic_text` trap, keytar gone.
6. Signing: Artifact Signing's name, eligibility and non-instant reputation; EV no longer skips SmartScreen; HSM keys
   and the 460-day cap; notarization with notarytool and stapling.
7. Updates from a custom domain (never `r2.dev`), the macOS zip target, no private GitHub provider.
8. OAuth through the system browser with PKCE and a loopback redirect; KVKK transfers by standard contract; consent
   for telemetry; the privacy manifest scoped to the Mac App Store; Playwright's fuse caveat.
9. The scaffold still ships what the pack says it ships, and neither pack carries a version number in any shape.

Guards read emphasis-stripped, whitespace-collapsed text and pin the clause that carries the force, so a reversed verb
fails. The cheapest way past (2) is a price in words ("ninety-nine dollars"); the check catches the shapes agents copy
from a vendor page (`$99`, `15%`), and the pack's review catches the rest.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "desktop-app" / "72-desktop.md"
DOMAIN = RULES / "desktop-app" / "00-domain-desktop-app.md"
TEMPLATE = ROOT / "templates" / "desktop-app"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text))


def _body(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("\n---\n", 1)[1]


def _section(path: Path, heading: str) -> str:
    """The text under the first heading that starts with `heading`, up to the next heading of the same level."""
    out, level, fence = [], 0, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"(#+) (.*)", line)
        if m and level and len(m.group(1)) <= level:
            break
        if m and not level and m.group(2).startswith(heading):
            level = len(m.group(1))
            continue
        if level:
            out.append(line)
    assert level, f"{path.name} lost its § {heading} heading"
    return _plain("\n".join(out))


def _has(text: str, *phrases: str) -> None:
    for phrase in phrases:
        assert phrase in text, f"lost: {phrase!r}"


@pytest.mark.parametrize("path", [PACK, DOMAIN], ids=["72", "00"])
def test_stamps(path: Path) -> None:
    head = path.read_text(encoding="utf-8").split("---", 2)[1]
    assert re.search(r"^currency_pass: \d{4}-\d{2}-\d{2}$", head, re.M), (
        f"{path.name} lost its currency_pass stamp"
    )


def test_domain_names_the_live_loaders() -> None:
    head = DOMAIN.read_text(encoding="utf-8").split("-->", 1)[0]
    loaders = re.findall(r"commands/_sources/[\w-]+\.md", head)
    assert loaders, "00 no longer names the planner commands that load it"
    for rel in loaders:
        assert "00-domain-desktop-app.md" in (ROOT / rel).read_text(encoding="utf-8"), (
            f"00 says {rel} loads it, but {rel} does not name it"
        )
    assert "docs/traycer" not in head, "00 points at the retired Traycer planner again"


def test_domain_copies_no_price_or_rate() -> None:
    found = re.findall(r"\$\s?\d|\d\s?%", _plain(_body(DOMAIN)))
    assert not found, f"00 copies a value 72 owns: {found}"


def test_domain_cites_resolve() -> None:
    cites = []
    for m in re.finditer(
        r"`72(?:-desktop\.md)?`((?:\s*[+·]?\s*§ [^§\n]+)+)", DOMAIN.read_text(encoding="utf-8")
    ):
        for seg in re.findall(r"§ ([^§]+?)(?=\s*[+·]\s*§|$)", m.group(1)):
            seg = re.split(r"\.(?:\s|$)|\*\*|;", seg)[0].strip()
            if seg.count(")") > seg.count("("):
                seg = seg[: seg.rindex(")")].strip()
            cites.append(seg)
    assert len(cites) >= 9, f"the cite parser found only {cites}"
    headings = [
        ln.lstrip("#").strip()
        for ln in PACK.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]
    for cite in cites:
        assert any(h.startswith(cite.strip()) for h in headings), (
            f"00 cites 72 § {cite}, which does not exist"
        )


def test_version_policy() -> None:
    s = _section(PACK, "Framework Choice")
    _has(
        s,
        "supports only the three newest stable majors, each on its latest minor",
        "move to the next major before yours leaves the window",
        "Electron's own docs recommend Electron Forge",
        "electron-builder is maintained by the community",
    )
    assert not re.search(r"Electron \d", _plain(PACK.read_text(encoding="utf-8"))), (
        "72 names an Electron version again"
    )


def test_renderer_lockdown() -> None:
    s = _section(PACK, "Process Model")
    _has(
        s,
        "contextIsolation: true",
        "nodeIntegration: false",
        "sandbox: true",
        "turning context isolation off also turns the sandbox off",
        "Electron approves every permission request",
        "setPermissionRequestHandler",
        "compare with Node's URL parser, never a string prefix",
        "setWindowOpenHandler(() => ({ action: 'deny' }))",
        "event.senderFrame.origin",
        "Check the frame's origin, not its URL",
        "never hand a renderer callback straight to ipcRenderer.on",
    )


def test_fuses() -> None:
    s = _section(PACK, "Fuses")
    for fuse, setting in (
        ("runAsNode", "off"),
        ("enableNodeOptionsEnvironmentVariable", "off"),
        ("enableNodeCliInspectArguments", "off in release builds"),
        ("enableCookieEncryption", "on"),
        ("enableEmbeddedAsarIntegrityValidation + onlyLoadAppFromAsar", "on"),
        ("grantFileProtocolExtraPrivileges", "off"),
    ):
        assert f"| {fuse} | {setting} |" in s, f"the fuse row {fuse} no longer says {setting}"
    _has(s, "it is not a security control")


def test_storage() -> None:
    s = _section(PACK, "Local Persistence")
    _has(
        s,
        "a random key needs no slow key derivation, so pass it raw",
        "key = \"x'${hexKey}'\"",
        "PBKDF2 with HMAC-SHA512, 256,000 iterations — above OWASP's floor for that hash",
    )
    assert s.index("cipher = 'sqlcipher'") < s.index("key = "), (
        "the cipher must be chosen before the key"
    )
    c = _section(PACK, "Credential Storage")
    _has(
        c,
        "which was archived in 2022",
        "encryptStringAsync",
        "getSelectedStorageBackend() === 'basic_text'",
        "encrypts with a hardcoded password",
        "not from other apps running as the same user",
    )
    sample = c.split("async function storeSecret", 1)[1].split("async function loadSecret", 1)[0]
    assert "=== 'basic_text'" in sample and "throw new Error" in sample, (
        "the storeSecret sample no longer refuses the basic_text backend"
    )


def test_signing() -> None:
    s = _section(PACK, "Code Signing")
    _has(
        s,
        "Azure Artifact Signing (formerly Trusted Signing)",
        "Organisations in the US, Canada, the EU and the UK; individuals in the US and Canada only",
        "not instant",
        "No longer skips SmartScreen (since 2024)",
        "Artifact Signing when the legal entity is eligible; otherwise an OV certificate held in a cloud signing service",
        "hardware security module since 2023-06-01",
        "caps certificate validity at 460 days from 2026-03-01",
        "cannot be expedited",
        "xcrun notarytool",
        "a ZIP cannot",
        "Smart App Control",
    )


def test_updates() -> None:
    s = _section(PACK, "Auto-Update")
    _has(
        s,
        "url: https://updates.<your-domain>/${os}",
        "says it is for development only",
        "DMG plus the zip target on macOS",
        "the app must be signed or it will not update",
        "GitHub Releases on a private repo",
        "Production updates from r2.dev",
    )
    assert "pub-" not in s, "72 points auto-update at an r2.dev URL again"


def test_auth_compliance_testing() -> None:
    a = _section(PACK, "Authentication")
    _has(
        a,
        "always with PKCE",
        "Google no longer supports custom URI schemes for desktop clients",
        "listen(0, '127.0.0.1'",
    )
    k = _section(PACK, "KVKK / GDPR Compliance")
    _has(
        k,
        "as amended by Law No. 7499 from 2024-06-01",
        "notified to the Authority within five business days of signing",
        "Explicit consent is now only an exception for incidental transfers",
        "falls under ePrivacy Art. 5(3)",
        "so it needs consent unless strictly necessary",
    )
    p = _section(PACK, "Apple Privacy Manifest")
    _has(p, "Apple's list does not name macOS", "Apple states no manifest check for notarization")
    t = _section(PACK, "Testing")
    _has(
        t,
        "Playwright's Electron support is experimental and needs the enableNodeCliInspectArguments fuse left on",
        "its repository is archived",
    )


def test_scaffold_ships_what_the_pack_says() -> None:
    main = _plain((TEMPLATE / "electron" / "main.js").read_text(encoding="utf-8"))
    for setting in ("nodeIntegration: false", "contextIsolation: true", "sandbox: true"):
        assert setting in main, f"the scaffold no longer sets {setting}"
    pkg = json.loads((TEMPLATE / "package.json").read_text(encoding="utf-8"))
    assert "electron-builder" in pkg["devDependencies"], (
        "the scaffold no longer packages with electron-builder"
    )
    _has(
        _section(PACK, "The fleet today"),
        "packaged with electron-builder",
        "ships no preload file and no update feed yet",
    )


def test_no_version_literals() -> None:
    vre = _load("vision72", ROOT / "tests" / "test_vision_pack.py").VERSION_RE
    # algorithm and standard names carry digits but version nothing the packs recommend
    # and so do pack filenames, the planning pack's Fork/Epic labels, IP addresses and API path segments
    names = r"PBKDF2|HMAC-SHA512|Ed25519|RFC \d+|\b\d\d-[a-z0-9-]+\.md|\b(?:Fork|Epic) \d|\b\d+(?:\.\d+){3}\b|/v\d+\b"
    for path in (PACK, DOMAIN):
        found = vre.findall(re.sub(names, "", _plain(_body(path))))
        assert not found, f"version literals in {path.name}: {found}"


@pytest.mark.parametrize("word", ["Kilo", "Traycer"])
def test_no_retired_routes(word: str) -> None:
    for path in (PACK, DOMAIN):
        assert word not in path.read_text(encoding="utf-8"), (
            f"{path.name} names the retired route {word}"
        )


def test_cited_packs_exist() -> None:
    for path in (PACK, DOMAIN):
        for ref in set(
            re.findall(r"`(?:core|desktop-app)/[\w-]+\.md`", path.read_text(encoding="utf-8"))
        ):
            assert (RULES / ref.strip("`")).is_file(), (
                f"{path.name} cites {ref}, which does not exist"
            )
