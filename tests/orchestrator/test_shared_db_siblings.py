"""The app-role cutover's shared-database scan sees template-supplied shape (W-989653a7)."""

from pathlib import Path

import pytest

from fabrik import spec_loader
from fabrik.orchestrator.infrastructure import AppRoleRefusalError, _shared_db_siblings

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _templates_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """The scan merges sibling templates from ``spec_loader.FABRIK_ROOT``; pin it to this checkout so
    the tests read the templates/ they ship with (otherwise it can resolve to the hub /opt/fabrik)."""
    monkeypatch.setattr(spec_loader, "FABRIK_ROOT", REPO)


def test_shared_db_sibling_with_template_needs_database_is_counted(tmp_path):
    """A sibling whose needs_database comes only from its template (saas-skeleton) is counted."""
    me = tmp_path / "me.yaml"
    me.write_text(
        "id: me\ntemplate: python-api\nshape:\n  needs_database: true\ndepends:\n  postgres: shared_db\n"
    )
    sib = tmp_path / "sib.yaml"
    sib.write_text("id: sib\ntemplate: saas-skeleton\ndepends:\n  postgres: shared_db\n")
    assert _shared_db_siblings("shared_db", me) == ["sib.yaml"]


def test_shared_db_sibling_with_unresolvable_template_is_skipped(tmp_path):
    """A sibling whose template name cannot resolve (NUL byte) is read raw — no crash, not a database spec."""
    me = tmp_path / "me.yaml"
    me.write_text("id: me\ntemplate: python-api\nshape:\n  needs_database: true\n")
    sib = tmp_path / "sib.yaml"
    sib.write_text('id: sib\ntemplate: "sa\\0as"\ndepends:\n  postgres: me\n')
    assert _shared_db_siblings("me", me) == []


def _own_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defaults: str) -> Path:
    """A templates root with one template, ``t``, whose defaults.yaml holds ``defaults``."""
    root = tmp_path / "root"
    (root / "templates" / "t").mkdir(parents=True)
    (root / "templates" / "t" / "defaults.yaml").write_text(defaults)
    monkeypatch.setattr(spec_loader, "FABRIK_ROOT", root)
    specs = tmp_path / "specs"
    specs.mkdir()
    me = specs / "me.yaml"
    me.write_text("id: me\ntemplate: t\nshape:\n  needs_database: true\n")
    return me


@pytest.mark.parametrize("defaults", ["shape: [unclosed\n", "- a list\n", "shape: [a]\n"])
def test_shared_db_sibling_with_unusable_template_refuses(tmp_path, monkeypatch, defaults):
    """A sibling whose template defaults cannot be merged refuses the cutover — the scan would otherwise
    guess that it is not a database spec."""
    me = _own_templates(tmp_path, monkeypatch, defaults)
    (me.parent / "sib.yaml").write_text("id: sib\ntemplate: t\n")
    with pytest.raises(AppRoleRefusalError, match="sib.yaml"):
        _shared_db_siblings("me", me)


def test_shared_db_scan_merges_only_the_template_shape(tmp_path, monkeypatch):
    """Only the template's shape: block merges: a template depends: default never renames a sibling's
    database (a full merge would make this sibling resolve to ``me`` and count)."""
    me = _own_templates(
        tmp_path, monkeypatch, "shape:\n  needs_database: true\ndepends:\n  postgres: me\n"
    )
    (me.parent / "sib.yaml").write_text("id: sib\ntemplate: t\n")
    assert _shared_db_siblings("me", me) == []
