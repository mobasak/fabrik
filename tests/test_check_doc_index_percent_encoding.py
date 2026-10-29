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
        ("docs/en–dash.md", "docs/en%E2%80%93dash.md"),
        ("docs/a, b (v2).md", "docs/a,%20b%20%28v2%29.md"),
    ],
    ids=["space", "literal-percent", "literal-hash", "utf8-lowercase", "utf8-upper", "parens"],
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


@pytest.mark.parametrize("name", ["docs/a%41.md", "docs/a%20b.md"], ids=["pct41", "pct20"])
def test_a_file_whose_real_name_holds_pct_xx_linked_by_that_name_still_resolves(
    monkeypatch, tmp_path, capsys, name: str
) -> None:
    """Decoding alone turned `docs/a%41.md` into `docs/aA.md`: the link as WRITTEN must still count
    in both gate rows (review pass 1, A2)."""
    import check_doc_links as cdl

    rc, out = _run(monkeypatch, tmp_path, capsys, [name], f"- [Doc]({name})\n")
    assert "names missing path" not in out, out
    assert rc == 0, out
    monkeypatch.setattr(cdl, "REPO", tmp_path)
    assert cdl._resolves(name, tmp_path / "INDEX.md") is True


def test_a_nul_escape_is_a_finding_in_both_rows_never_a_traceback(
    monkeypatch, tmp_path, capsys
) -> None:
    """`%00` decodes to a NUL and `Path.resolve()` raises on it: check_doc_links must answer
    "broken", check_doc_index must name the missing path (review pass 1, A1)."""
    import check_doc_links as cdl

    rc, out = _run(
        monkeypatch, tmp_path, capsys, ["docs/b.md"], "- [B](docs/b.md)\n- [N](docs/x%00.md)\n"
    )
    assert rc == 1, out
    assert "names missing path" in out, out
    monkeypatch.setattr(cdl, "REPO", tmp_path)
    assert cdl._resolves("docs/x%00.md", tmp_path / "INDEX.md") is False


def test_an_escaped_slash_is_never_a_separator(monkeypatch, tmp_path, capsys) -> None:
    """`%2F` stays literal: `docs%2Fsub%2Fx.md` neither resolves nor credits `docs/sub/x.md` by
    PATH. (b)'s basename fallback still matches `x.md` inside the text — pre-existing — so the
    observable is the shared-name advisory: neither `x.md` is credited by path, both are advised."""
    import check_doc_links as cdl

    rc, out = _run(
        monkeypatch,
        tmp_path,
        capsys,
        ["docs/sub/x.md", "docs/other/x.md"],
        "- [X](docs%2Fsub%2Fx.md)\n",
    )
    advisories = [ln for ln in out.splitlines() if "doc indexed only by a shared name" in ln]
    assert len(advisories) == 2, out
    monkeypatch.setattr(cdl, "REPO", tmp_path)
    assert cdl._resolves("docs%2Fsub%2Fx.md", tmp_path / "INDEX.md") is False


def test_a_percent_escaped_basename_only_mention_indexes_the_doc(
    monkeypatch, tmp_path, capsys
) -> None:
    """The basename half of (b) reads the decoded text too: a relative `my%20notes.md` link."""
    rc, out = _run(
        monkeypatch, tmp_path, capsys, ["docs/my notes.md"], "- [Notes](my%20notes.md)\n"
    )
    assert "not in INDEX.md" not in out, out
    assert rc == 0, out


def test_an_escaped_full_path_spares_its_doc_the_shared_name_advisory(
    monkeypatch, tmp_path, capsys
) -> None:
    """The PATH half of (b) reads the decoded text: `docs/a/my%20notes.md` names `docs/a/...`
    by path, so only `docs/b/...` (indexed by the shared basename alone) is advised on."""
    rc, out = _run(
        monkeypatch,
        tmp_path,
        capsys,
        ["docs/a/my notes.md", "docs/b/my notes.md"],
        "- [A](docs/a/my%20notes.md)\n",
    )
    advisories = [ln for ln in out.splitlines() if "doc indexed only by a shared name" in ln]
    assert len(advisories) == 1, out
    assert "only by a shared name: docs/b/my notes.md" in advisories[0], out


def test_both_rows_decode_with_one_contract() -> None:
    import check_doc_links as cdl

    for text in ["a%20b", "a%2Fb", "a%2fb", "%2520", "%E9", "%e2%80%93", "%00", "100%", "%zz", ""]:
        assert cdi._pct_decode(text) == cdl.pct_decode(text), text


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
    """Paths are read with surrogateescape (`_printable` exists for them), so the decode must use it
    too: a strict decode raises or yields U+FFFD, which never matches. Unindexed the name is a
    finding naming the doc; linked with its byte escaped (`%E9`) it is indexed."""
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
    assert "live doc not in INDEX.md: docs/caf" in capsys.readouterr().out
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


def _links(monkeypatch, tmp_path, capsys) -> list[str]:
    """Run check_doc_links over the repo `_run` just built and return its broken-ref lines."""
    import json

    import check_doc_links as cdl

    monkeypatch.setattr(cdl, "REPO", tmp_path)
    monkeypatch.setattr(cdl.sys, "argv", ["check_doc_links.py", "--json"])
    cdl.main()
    return json.loads(capsys.readouterr().out)["broken"]


@pytest.mark.parametrize(
    ("docs", "index", "missing"),
    [
        (["docs/a(b).md"], "- [A](docs/a(b).md)\n", None),
        (["docs/b.md"], "- [B](docs/b.md)\n- [G](docs/g(o)ne.md)\n", "docs/g(o)ne.md"),
        (["docs/t.md"], '- [T](docs/t.md "Title")\n', None),
        (["docs/t.md"], '- [T](docs/t.md "T")\n- [G](docs/g(1).md "Title")\n', "docs/g(1).md"),
        (["docs/t.md"], "- [T](docs/t.md 'T')\n- [G](docs/g(2).md 'Title')\n", "docs/g(2).md"),
        (["docs/t.md"], "- [T](docs/t.md (T))\n- [G](docs/g(3).md (Title))\n", "docs/g(3).md"),
        (["docs/a b.md"], "- [A](<docs/a b.md>)\n", None),
        (["docs/b.md"], "- [B](docs/b.md)\n- [G](<docs/gone x.md>)\n", "docs/gone x.md"),
        (["docs/a_b.md"], "- [E](docs/a\\_b.md)\n", None),
        (["docs/a_b c.md"], "- [E](docs/a\\_b%20c.md)\n", None),
        (["docs/a_b%41.md"], "- [E](docs/a\\_b%41.md)\n", None),
        (["docs/b.md"], "- [B](docs/b.md)\n- [G](docs/g\\#x.md)\n", "docs/g#x.md"),
    ],
    ids=[
        "paren-live",
        "paren-missing",
        "titled-live",
        "double-titled-missing",
        "single-titled-missing",
        "paren-titled-missing",
        "angle-live",
        "angle-missing",
        "escaped-live",
        "escaped-and-encoded-live",
        "escaped-with-a-literal-percent-live",
        "escaped-hash-missing",
    ],
)
def test_every_commonmark_link_shape_is_graded_by_both_checks(
    monkeypatch, tmp_path, capsys, docs: list[str], index: str, missing: str | None
) -> None:
    """W-dd091f0d: both INDEX link readers stopped at the first `)` or space. A balanced-paren link
    to a live doc was truncated (`docs/a(b`) and reported missing; a titled or `<angle>` link never
    matched, so a link to a MISSING doc was never examined. Direction (a) of check_doc_index and
    check_doc_links must both read every shape CommonMark renders as a link, and an escaped link
    (`docs/a\\_b.md`, also percent-encoded or naming a literal `%41`) counts for direction (b)
    exactly when it counts for (a). Every missing target holds a paren, a space or a `#`, which
    check_doc_links' BARE-path reader cannot match, so only its link reader can report it."""
    rc, out = _run(monkeypatch, tmp_path, capsys, docs, index)
    broken = _links(monkeypatch, tmp_path, capsys)
    if missing is None:
        assert rc == 0, out
        assert broken == [], broken
    else:
        assert rc == 1, out
        assert f"INDEX.md names missing path: {missing}" in out, out
        assert broken == [f"INDEX.md: broken ref -> {missing}"], broken


def test_a_link_whose_text_spans_a_line_break_is_graded(monkeypatch, tmp_path, capsys) -> None:
    """CommonMark link text may span a line break (`[Notes⏎](docs/gone.md)`). A line-by-line
    read of INDEX.md (a review-pass fix, reverted) put the `[` and the `](` on different lines and
    passed the missing doc; direction (a) reads the whole text, as the pre-change regex did."""
    rc, out = _run(
        monkeypatch,
        tmp_path,
        capsys,
        ["docs/a.md"],
        "- [Notes\n](docs/gone.md)\n- [A](docs/a.md)\n",
    )
    assert rc == 1, out
    assert "INDEX.md names missing path: docs/gone.md" in out, out


def test_an_added_code_path_indexed_percent_encoded_needs_no_advisory(
    monkeypatch, tmp_path, capsys
) -> None:
    """Direction (c) compared the RAW INDEX text only, so a row naming `scripts/a%20b.py` — the
    spelling (a) and (b) accept — still earned "added code file not in INDEX.md". A bare encoded
    mention counts through the decoded text, an escaped link through the parsed link set."""
    rc, out = _run(
        monkeypatch,
        tmp_path,
        capsys,
        ["scripts/a b.py", "scripts/a_b.py", "scripts/c d.py"],
        "- scripts/a%20b.py (a bare mention)\n- [x](scripts/a\\_b.py)\n",
    )
    assert "added code file not in INDEX.md: scripts/a b.py" not in out, out
    assert "added code file not in INDEX.md: scripts/a_b.py" not in out, out
    assert "added code file not in INDEX.md: scripts/c d.py" in out, out  # still graded


def test_a_non_ascii_added_code_path_is_examined(monkeypatch, tmp_path, capsys) -> None:
    """`git diff --name-only` without `-z` C-quoted a non-ASCII name (`"scripts/caf\\303\\251.py"`),
    which never starts with a code root, so such an added file was never examined at all."""
    rc, out = _run(
        monkeypatch,
        tmp_path,
        capsys,
        ["scripts/café.py", "scripts/naïve.py"],
        "- [c](scripts/café.py)\n",
    )
    assert "added code file not in INDEX.md: scripts/café.py" not in out, out
    assert "added code file not in INDEX.md: scripts/naïve.py" in out, out


def test_both_link_readers_find_one_set_of_targets() -> None:
    """check_doc_index carries its own copy of the reader (no enforcement check imports a sibling);
    the two must return one output."""
    import check_doc_links as cdl

    for text in [
        "[a](docs/a(b).md) and [b](docs/b.md#frag)",
        "[t](docs/t.md \"T\") [u](docs/u.md 'U') [v](docs/v.md (V))",
        "[a](<docs/a b.md>) [n](<docs/n.md>)",
        r"[e](docs/e\(x\).md) [i](![img](docs/i.png)",
        "[bad](docs/a(b.md [open](docs/x.md",
        '[x](#only-fragment) [y]() [z](docs/z.md "unterminated)',
        r"[s](docs/a\ b.md) [h](docs/a\#b.md#frag) [w](docs/x](docs/gone.md).md)",
        r"[e](docs/a\_b.md) [g](docs/g(o)ne.md) " + '[t](docs/x.md "see ](docs/gone.md)")',
        r"\[x](docs/a.md) [a \\](docs/b.md)",
        "[a](docs/a(b.md ) [n](<docs/a\nb.md>) " + r"[q](<docs/a\>b.md>) [c](docs/a\).md)",
        "plain ](docs/stray.md) " + r'\](docs/a.md "see [x](docs/gone.md)") [a] \](docs/g.md)',
        "[![i](docs/i.png)](docs/x.md)",
        r'C:\\[a](docs/x.md) [e](docs/a\_b%20c.md) [p](docs/a\_b%41.md) [h](docs/g\#x.md "T" )',
        "",
    ]:
        assert list(cdi.link_targets(text)) == list(cdl.link_targets(text)), text


@pytest.mark.parametrize(
    ("text", "targets"),
    [
        (r"[s](docs/a\ b.md)", []),  # `\ ` escapes nothing: the space ends it, so no link
        (r"[h](docs/a\#b.md#frag)", ["docs/a#b.md"]),  # an escaped `#` is part of the path
        ("[w](docs/x](docs/gone.md).md)", ["docs/x](docs/gone.md).md"]),  # one link, not two
        ('[t](docs/x.md "see ](docs/gone.md)")', ["docs/x.md"]),  # a title holds no link
        ('[t](docs/x.md "T")', ["docs/x.md"]),
        ("[t](docs/x.md 'T')", ["docs/x.md"]),
        ("[t](docs/x.md (T))", ["docs/x.md"]),
        ("[a](docs/a(b.md )", []),  # an unclosed paren is no destination
        ("[a](<docs/a\nb.md>)", []),  # an angle destination never spans a line
        (r"[a](<docs/a\>b.md>)", ["docs/a>b.md"]),  # `\>` stays inside the angle form
        (r"[e](docs/e\(x\).md)", ["docs/e(x).md"]),
        (r"[e](docs/a\).md)", ["docs/a).md"]),  # an escaped `)` neither closes nor counts
        ("plain ](docs/stray.md) text", []),  # no `[` before it: not a link
        (r"\](docs/a.md)", []),  # an escaped `]` closes nothing
        (r"[a] \](docs/gone.md)", []),  # ... even after an opener
        (r'- \](docs/a.md "see [x](docs/gone.md)")', ["docs/gone.md"]),  # the real link survives
        ("[![i](docs/i.png)](docs/x.md)", ["docs/i.png", "docs/x.md"]),  # an image inside a link
        (r"C:\\[a](docs/x.md)", ["docs/x.md"]),  # `\\` is an escaped backslash: the `[` opens
        (r"\[x](docs/a.md)", []),  # an escaped `[` opens nothing
        (r"[a \\](docs/b.md)", ["docs/b.md"]),  # an even run before `]`: it still closes
    ],
    ids=[
        "escaped-space",
        "escaped-hash",
        "bracket-in-destination",
        "link-in-title",
        "double-quoted-title",
        "single-quoted-title",
        "paren-title",
        "unbalanced-paren",
        "angle-across-a-line",
        "escaped-angle-close",
        "escaped-parens",
        "escaped-unbalanced-close",
        "no-opener",
        "escaped-closer",
        "escaped-closer-after-an-opener",
        "stray-closer-before-a-real-link",
        "image-inside-a-link",
        "opener-after-an-escaped-backslash",
        "escaped-opener",
        "closer-after-an-even-backslash-run",
    ],
)
def test_the_reader_follows_commonmark_on_escapes_and_consumed_links(
    text: str, targets: list[str]
) -> None:
    import check_doc_links as cdl

    assert list(cdl.link_targets(text)) == targets


@pytest.mark.parametrize(
    ("text", "targets"),
    [
        ('[t](docs/x.md\n"T")', ["docs/x.md"]),  # a line ending before the title
        ("[t](docs/x.md \n  'T')", ["docs/x.md"]),  # spaces, the line ending, then the title
        ("[t](docs/x.md\n)", ["docs/x.md"]),  # a line ending before the closing paren
        ('[t](docs/x.md "T"\n)', ["docs/x.md"]),  # ... after a title too
        ("[t](\ndocs/x.md)", ["docs/x.md"]),  # a line ending before the destination
        ("[t](docs/x.md\n\n)", []),  # a blank line ends the link: two line endings never do
        ('[t](docs/x.md\n\n"T")', []),
        ("[t](docs/x.md\n  \n)", []),  # a whitespace-only line is a blank line too
        ('[t](docs/x.md\n\t"T"\t\n\t)', ["docs/x.md"]),  # tabs either side of each line ending
        # review pass 1 (both finders): check_doc_index reads INDEX.md as bytes, so CRLF and a lone CR
        # are line endings as CommonMark counts them
        ('[t](docs/x.md\r\n"T")', ["docs/x.md"]),
        ("[t](\r\ndocs/x.md\r\n)", ["docs/x.md"]),
        ("[t](docs/x.md\r)", ["docs/x.md"]),
        ("[t](docs/x.md\r\n\r\n)", []),
    ],
    ids=[
        "newline-before-title",
        "spaces-newline-before-title",
        "newline-before-close",
        "newline-after-title",
        "newline-before-destination",
        "blank-line-before-close",
        "blank-line-before-title",
        "whitespace-only-line",
        "tab-continuations",
        "crlf-before-title",
        "crlf-around-destination",
        "lone-cr-before-close",
        "blank-crlf-line",
    ],
)
def test_both_readers_take_one_line_ending_in_a_links_whitespace(
    text: str, targets: list[str]
) -> None:
    """W-55905ee1 (W-f11e740e review, slice A Haiku): CommonMark lets the whitespace around a link's
    destination, before its title and before its `)` hold up to one line ending; `_TITLE_CLOSE_RE`
    allowed spaces and tabs only, so docs_updater (which feeds whole documents) skipped a link its
    regex fallback graded. Both copies of the reader take the same shapes (the parity test pins them)."""
    import check_doc_links as cdl

    assert list(cdl.link_targets(text)) == targets
    assert list(cdi.link_targets(text)) == targets
