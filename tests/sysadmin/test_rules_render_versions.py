"""Version injection (D-062 — no hand-owned version literals in packs).

Pins: span rewriting is exact and idempotent; unknown keys refuse loudly; the
loose sweep flags only UNMARKED literals (a marked span never fires); and the
live corpus round-trips — file 1's spans agree with versions.yaml at HEAD.
"""

from scripts.sysadmin.rules_render_versions import _LOOSE, _SPAN, inject_text, load_versions


def test_span_injection_exact_and_idempotent():
    text = "FROM python:<!--v:python_stable-->3.13<!--/v-->-slim"
    out, n, unknown = inject_text(text, {"python_stable": "3.14"})
    assert out == "FROM python:<!--v:python_stable-->3.14<!--/v-->-slim"
    assert n == 1 and unknown == []
    again, n2, _ = inject_text(out, {"python_stable": "3.14"})
    assert again == out and n2 == 0


def test_unknown_key_surfaces_not_silently_skipped():
    _, _, unknown = inject_text("<!--v:nope-->x<!--/v-->", {})
    assert unknown == ["nope"]


def test_loose_sweep_ignores_marked_spans_flags_unmarked():
    marked = "FROM python:<!--v:python_stable-->3.14<!--/v-->-slim"
    assert not _LOOSE.search(_SPAN.sub("", marked))
    assert _LOOSE.search("FROM python:3.14-slim")
    assert _LOOSE.search("use node:24 here")


def test_live_corpus_file1_round_trips():
    from pathlib import Path

    versions = load_versions()
    text = Path("/opt/fabrik/.windsurf/rules/core/10-python.md").read_text(encoding="utf-8")
    spans = _SPAN.findall(text)
    assert len(spans) >= 2  # python_stable + debian_codename
    _, changed, unknown = inject_text(text, versions)
    assert changed == 0 and unknown == []  # HEAD agrees with the source


def test_loose_sweep_catches_name_version_prose_not_status_codes():
    # The docker-tag-only sweep was blind to prose literals — the operator's
    # re-ask found 4 in an already-passed file. Status codes must never fire.
    assert _LOOSE.search("use list[str] (Python 3.9+)")
    assert _LOOSE.search("SQLAlchemy 2.0 requires it")
    assert _LOOSE.search("Node 24 is the LTS")
    assert _LOOSE.search("Debian 13 shipped")
    assert not _LOOSE.search("FastAPI 500 responses")  # status code, not a version
    assert not _LOOSE.search("returns 404 or 500")
    assert not _LOOSE.search("Python services: 8000-8099")


def test_file1_carries_zero_unmarked_version_literals():
    # The exemplar's contract under D-062: spans only, no prose literals.
    from pathlib import Path

    text = Path("/opt/fabrik/.windsurf/rules/core/10-python.md").read_text(encoding="utf-8")
    assert not _LOOSE.search(_SPAN.sub("", text))
