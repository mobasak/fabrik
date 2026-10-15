"""The app-role cutover's shared-database scan sees template-supplied shape (W-989653a7)."""

from fabrik.orchestrator.infrastructure import _shared_db_siblings


def test_shared_db_sibling_with_template_needs_database_is_counted(tmp_path):
    """A sibling whose needs_database comes only from its template (saas-skeleton) is counted."""
    me = tmp_path / "me.yaml"
    me.write_text(
        "id: me\ntemplate: python-api\nshape:\n  needs_database: true\ndepends:\n  postgres: shared_db\n"
    )
    sib = tmp_path / "sib.yaml"
    sib.write_text("id: sib\ntemplate: saas-skeleton\ndepends:\n  postgres: shared_db\n")
    assert _shared_db_siblings("shared_db", me) == ["sib.yaml"]
