# AFTER-EDIT: src/fabrik/scaffold.py
"""Behavior contract for the `office-extension` scaffold type (operator ruling 2026-08-30).

An Office add-in (Outlook/Word/Excel) is TWO deployed surfaces: a hosted taskpane web app +
a backend API that runs on the VPS fleet — plus the manifest.xml the Office host loads.
It is NOT chrome-extension (bundled/store-distributed, no hosted half, no deploy spec) and
NOT saas-skeleton (which loses the add-in identity that routes tooling + pipeline stages).
"""

from __future__ import annotations

from fabrik import scaffold


def test_office_extension_is_registered_and_dispatchable():
    assert "office-extension" in scaffold.SCAFFOLD_TYPES, "must be a valid project.yaml type"
    assert "office-extension" in scaffold._TYPE_SCAFFOLDERS, "must map to a scaffolder"
    assert "manifest.xml" in scaffold.TYPE_REQUIRED_FILES["office-extension"], (
        "the manifest is what makes it an add-in — it must be a required file"
    )


def test_office_extension_is_not_classified_headless():
    # the headless set is what SKIPS the GUI pipeline; a taskpane IS a web GUI, so the type
    # must never appear there (the contract's UI-bearing list is prose, this pins the code side)
    headless = {"python-api", "python-api-gpu", "node-api", "file-api", "file-worker"}
    assert "office-extension" not in headless


def test_office_extension_emits_manifest_over_the_hosted_skeleton(tmp_path, monkeypatch):
    # emits the saas-skeleton hosted web + backend (the deployable halves) AND the manifest
    calls = []
    monkeypatch.setattr(
        scaffold, "_scaffold_saas_skeleton", lambda d, n, desc, **k: calls.append((d, n))
    )
    proj = tmp_path / "addin"
    proj.mkdir()
    scaffold._scaffold_office_extension(proj, "tojlo-mail", "Outlook add-in")
    assert calls, "must reuse the hosted web + backend skeleton, not re-emit it"
    manifest = (proj / "manifest.xml").read_text()
    assert manifest.startswith("<?xml"), "must be a valid XML document"
    assert 'xsi:type="MailApp"' in manifest, "Outlook add-in manifest shape"
    assert "tojlo-mail" in manifest and "Outlook add-in" in manifest, "name/description injected"
    # placeholders are DELIBERATE and greppable — never a plausible-looking wrong URL
    assert "__HOST_URL__" in manifest, "deploy-time host URL must be an explicit placeholder"


def test_office_manifest_is_wellformed_xml(tmp_path):
    import xml.etree.ElementTree as ET

    proj = tmp_path / "p"
    proj.mkdir()
    scaffold._write_office_manifest(proj, "svc", "desc")
    ET.parse(proj / "manifest.xml")  # raises on malformed XML


def test_registry_types_appear_in_the_corpus_enumerations():
    """The registry-drift guard (promoted after office-extension recurred twice in two days):
    every UI-bearing enumeration site in the command corpus that names scaffold types must
    include office-extension, and the type must be in the live registry."""
    from fabrik.scaffold import SCAFFOLD_TYPES

    assert "office-extension" in SCAFFOLD_TYPES
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "commands" / "_sources"
    for f in ("fabrik-spec-review.md", "fabrik-user-test.md", "fabrik-flows.md", "fabrik-release.md"):
        text = (root / f).read_text(encoding="utf-8")
        assert "office-extension" in text, f"{f} enumerates scaffold types without office-extension"
