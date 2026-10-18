"""check_doc_index.py reads INDEX.md link targets percent-encoded on BOTH sides (W-7ae1169a).

Direction (a) — every INDEX target exists — decoded only `%20`; direction (b) — every live doc is
indexed — compared the RAW path. So `docs/my notes.md`, linked the correct markdown way as
`docs/my%20notes.md` under a human title, passed (a) and was reported "not in INDEX.md" by (b):
52 tracked docs fleet-wide carry a space. Its mirror had no remedy at all: a name holding a
literal `%` or `#` cannot be linked so that both sides agree. Each test builds a real git repo.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_doc_index as cdi  # noqa: E402


def _run(monkeypatch, tmp_path, capsys, docs: list[str], index: str) -> tuple[int, str]:
    """Commit `docs` (each a repo-relative path) and INDEX.md, run the check, return (rc, out)."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for rel in docs:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("# doc\n", encoding="utf-8")
    (tmp_path / "INDEX.md").write_text("# INDEX\n\n" + index, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])
    rc = cdi.main()
    return rc, capsys.readouterr().out


def test_a_spaced_doc_linked_percent_escaped_under_a_title_is_indexed(
    monkeypatch, tmp_path, capsys
) -> None:
    rc, out = _run(
        monkeypatch, tmp_path, capsys, ["docs/my notes.md"], "- [Notes](docs/my%20notes.md)\n"
    )
    assert "not in INDEX.md" not in out, out
    assert rc == 0, out


@pytest.mark.parametrize(
    ("name", "link"),
    [
        ("docs/a%20b.md", "docs/a%2520b.md"),  # a literal `%`: its escape is %25
        ("docs/a#b.md", "docs/a%23b.md"),  # a literal `#`: the raw form reads as an anchor
        ("docs/en–dash.md", "docs/en%E2%80%93dash.md"),  # a percent-encoded UTF-8 name
        ("docs/en–dash.md", "docs/en%e2%80%93dash.md"),  # the same, lowercase hex
        ("docs/R&D notes.md", "docs/R&D%20notes.md"),  # the space escaped, `&` left raw
        ("docs/a, b (v2).md", "docs/a,%20b%20%28v2%29.md"),  # parens must be escaped in a link
    ],
    ids=["literal-percent", "literal-hash", "utf8-escaped", "utf8-lowercase", "partial", "parens"],
)
def test_every_percent_escape_is_a_reachable_remedy(
    monkeypatch, tmp_path, capsys, name: str, link: str
) -> None:
    """Both directions read one percent-decoding contract, so every name has a link spelling."""
    rc, out = _run(monkeypatch, tmp_path, capsys, [name], f"- [The doc]({link})\n")
    assert "names missing path" not in out, out
    assert "not in INDEX.md" not in out, out
    assert rc == 0, out


@pytest.mark.parametrize(
    ("name", "link"),
    [
        ("docs/my notes.md", "docs/my%20notes.md"),
        ("docs/a%20b.md", "docs/a%2520b.md"),
        ("docs/a#b.md", "docs/a%23b.md"),
        ("docs/en–dash.md", "docs/en%e2%80%93dash.md"),
        ("docs/R&D notes.md", "docs/R&D%20notes.md"),
    ],
    ids=["space", "literal-percent", "literal-hash", "utf8-lowercase", "partial"],
)
def test_check_doc_links_resolves_every_remedy_check_doc_index_accepts(
    monkeypatch, tmp_path, name: str, link: str
) -> None:
    """check_doc_links scans INDEX.md in the SAME gate run and decoded only `%20`: every remedy
    above would have moved from a check_doc_index red to a check_doc_links "broken ref"."""
    import check_doc_links as cdl

    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text("# doc\n", encoding="utf-8")
    monkeypatch.setattr(cdl, "REPO", tmp_path)
    src = tmp_path / "INDEX.md"
    assert cdl._resolves(link, src) is True
    assert cdl._resolves("docs/gone%20x.md", src) is False  # a missing target stays broken


def test_a_spaced_doc_linked_raw_is_still_indexed(monkeypatch, tmp_path, capsys) -> None:
    """A CONTROL (green before and after): a bare path mention still counts as indexed."""
    rc, out = _run(monkeypatch, tmp_path, capsys, ["docs/my notes.md"], "- docs/my notes.md\n")
    assert rc == 0, out


def test_an_unindexed_spaced_doc_is_still_reported(monkeypatch, tmp_path, capsys) -> None:
    rc, out = _run(
        monkeypatch, tmp_path, capsys, ["docs/my notes.md", "docs/b.md"], "- [B](docs/b.md)\n"
    )
    assert rc == 1, out
    assert "live doc not in INDEX.md: docs/my notes.md" in out, out


def test_a_non_utf8_name_is_reported_and_reachable_never_a_traceback(
    monkeypatch, tmp_path, capsys
) -> None:
    """Paths are decoded with surrogateescape (`_printable` exists for them): a strict-UTF-8
    `quote()` of such a name raised UnicodeEncodeError. Unindexed it is a finding; linked with its
    byte escaped (`%E9`) it is indexed."""
    raw = b"docs/caf\xe9 x.md"
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text("# b\n", encoding="utf-8")
    with open(bytes(tmp_path) + b"/" + raw, "wb") as f:
        f.write(b"# doc\n")
    (tmp_path / "INDEX.md").write_text("# INDEX\n\n- [B](docs/b.md)\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])
    assert cdi.main() == 1
    assert "live doc not in INDEX.md" in capsys.readouterr().out
    (tmp_path / "INDEX.md").write_text(
        "# INDEX\n\n- [B](docs/b.md)\n- [Cafe](docs/caf%E9%20x.md)\n", encoding="utf-8"
    )
    rc = cdi.main()
    out = capsys.readouterr().out
    assert rc == 0, out


def test_a_percent_escaped_link_to_a_missing_doc_is_still_reported(
    monkeypatch, tmp_path, capsys
) -> None:
    rc, out = _run(
        monkeypatch, tmp_path, capsys, ["docs/b.md"], "- [B](docs/b.md)\n- [G](docs/gone%20x.md)\n"
    )
    assert rc == 1, out
    assert "INDEX.md names missing path: docs/gone x.md" in out, out
