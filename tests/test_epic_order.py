# AFTER-EDIT: scripts/epic_order.py
"""Tests for scripts/epic_order.py's --assign / --check --owners contract (T03a).

Every fixture lives under tmp_path — never docs/development/epics/ (the hub's own
epic store), per the ticket's Behavior Contract.
"""

import re
from pathlib import Path

import pytest
from scripts.epic_order import (
    _classify_fm_line,
    _parse_frontmatter,
    check_integrity,
    load_epics,
    main,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _REPO_ROOT / "docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md"
_CHECKLIST_PATH = (
    _REPO_ROOT
    / "docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md"
)
_SCRIPT_PATH = _REPO_ROOT / "scripts/epic_order.py"


def _schema_example_frontmatter() -> str:
    """The exact fenced ```yaml example block from EPIC-ARTIFACT-SCHEMA.md --
    read live so this test tracks the doc instead of a hand-copied
    approximation that could silently drift from it."""
    text = _SCHEMA_PATH.read_text(encoding="utf-8")
    fence_start = text.index("```yaml\n") + len("```yaml\n")
    fence_end = text.index("```", fence_start)
    return text[fence_start:fence_end]


def _write_epic(
    path: Path,
    number: int,
    deps: str = "[]",
    owner: str | None = None,
    body: str = "\n## Epic {n} — epic-{n}\n\nSome epic body text.\n",
) -> None:
    owner_line = f"owner: {owner}\n" if owner is not None else ""
    path.write_text(
        f"---\n"
        f"title: Epic {number} — epic-{number}\n"
        f"epic_n: {number}\n"
        f"slug: epic-{number}\n"
        f"depends_on: {deps}\n"
        f"parallel_with: []\n"
        f"owned_paths: []\n"
        f"{owner_line}"
        f"---\n" + body.format(n=number),
        encoding="utf-8",
    )


def _owner_line(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("owner:"):
            return line
    return None


def test_assign_round_robin_continues_across_phases(tmp_path, capsys):
    # Phase 1 (no deps): epics 1, 2. Phase 2 (depend on phase 1): epics 3, 4, 5.
    _write_epic(tmp_path / "e1.md", 1)
    _write_epic(tmp_path / "e2.md", 2)
    _write_epic(tmp_path / "e3.md", 3, deps="[1]")
    _write_epic(tmp_path / "e4.md", 4, deps="[1]")
    _write_epic(tmp_path / "e5.md", 5, deps="[2]")

    rc = main(["--epics-dir", str(tmp_path), "--assign", "alpha,beta,gamma"])
    assert rc == 0

    expected = {1: "alpha", 2: "beta", 3: "gamma", 4: "alpha", 5: "beta"}
    for n, owner in expected.items():
        assert _owner_line(tmp_path / f"e{n}.md") == f"owner: {owner}"

    assert "ASSIGN: OK" in capsys.readouterr().out


def test_assign_is_byte_idempotent(tmp_path):
    _write_epic(tmp_path / "e1.md", 1)
    _write_epic(tmp_path / "e2.md", 2)

    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha,beta"]) == 0
    before = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}
    mtimes_before = {p.name: p.stat().st_mtime_ns for p in sorted(tmp_path.iterdir())}

    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha,beta"]) == 0
    after = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}

    assert before == after
    # not written at all the second time around (mtime proves it, not just content)
    mtimes_after = {p.name: p.stat().st_mtime_ns for p in sorted(tmp_path.iterdir())}
    assert mtimes_before == mtimes_after


def test_assign_reassignment_replaces_single_line_not_duplicated(tmp_path):
    # Round 2 finding H: a reassignment (different names on a second run) must
    # REPLACE the one owner: line, never leave the old one behind duplicated.
    _write_epic(tmp_path / "e1.md", 1)
    _write_epic(tmp_path / "e2.md", 2, deps="[1]")

    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha,beta"]) == 0
    assert main(["--epics-dir", str(tmp_path), "--assign", "gamma,delta"]) == 0

    for name, expected in (("e1.md", "gamma"), ("e2.md", "delta")):
        lines = (tmp_path / name).read_text(encoding="utf-8").splitlines()
        owner_lines = [line for line in lines if line.startswith("owner:")]
        assert owner_lines == [f"owner: {expected}"], f"{name}: {owner_lines}"


def test_assign_append_adds_no_blank_line_in_frontmatter(tmp_path):
    # Every real epic predates the `owner:` field, so the very first --assign
    # hits the APPEND branch (no existing owner: line) on all of them. The
    # append must not leave a blank line before the closing "---" fence, and
    # the prose body after the frontmatter must be untouched.
    _write_epic(tmp_path / "e1.md", 1)
    path = tmp_path / "e1.md"
    _opening, before_frontmatter, before_prose_body = path.read_text(encoding="utf-8").split(
        "---\n", 2
    )
    assert "owner:" not in before_frontmatter  # sanity: this fixture has no owner: line yet

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_text(encoding="utf-8")
    assert "\n\n---" not in text, "blank line inside the frontmatter before the closing fence"
    _opening, after_frontmatter, after_prose_body = text.split("---\n", 2)
    assert after_frontmatter == before_frontmatter + "owner: beta\n"
    assert after_prose_body == before_prose_body


def test_assign_inserts_owner_after_owned_paths_in_real_shaped_frontmatter(tmp_path):
    # Round 2 finding G: EPIC-ARTIFACT-SCHEMA.md places `owner` between
    # `owned_paths` and `scaffold` — the writer must insert there, not always
    # at the tail (a real epic has scaffold/port/target_vps AFTER owned_paths).
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "kind: story\n"
        "title: Epic 1 — epic-1\n"
        "status: 0\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        'owned_paths: ["src/hello_api/**"]\n'
        "scaffold: python-api\n"
        "port: 8099\n"
        "target_vps: vps1\n"
        "---\n"
        "\n## Epic 1 — epic-1\n\nBody.\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    owned_idx = next(i for i, line in enumerate(lines) if line.startswith("owned_paths:"))
    assert lines[owned_idx + 1] == "owner: beta"
    assert lines[owned_idx + 2] == "scaffold: python-api"


def test_assign_preserves_crlf_line_endings(tmp_path):
    # Round 2 finding B: opening in universal-newline text mode silently
    # rewrites every CRLF to LF the first time --assign touches a file.
    original = (
        "---\r\n"
        "title: Epic 1 — epic-1\r\n"
        "epic_n: 1\r\n"
        "slug: epic-1\r\n"
        "depends_on: []\r\n"
        "parallel_with: []\r\n"
        "owned_paths: []\r\n"
        "---\r\n"
        "\r\n## Epic 1 — epic-1\r\n\r\nSome epic body text.\r\n"
    )
    path = tmp_path / "e1.md"
    path.write_bytes(original.encode("utf-8"))

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_bytes().decode("utf-8")
    assert "\n" not in text.replace("\r\n", ""), "a bare LF survived a CRLF file"
    assert text == original.replace("owned_paths: []\r\n", "owned_paths: []\r\nowner: beta\r\n")


def test_schema_example_block_strips_comments_from_every_top_level_value():
    # Round 5(H): _strip_unquoted_comment used to run ONLY inside the
    # block-list branch. Every TOP-LEVEL value in the schema's own worked
    # example carries a trailing comment -- `owned_paths: [...]  # comment`
    # no longer matched val.endswith("]") once the comment was attached, so
    # it fell through to the scalar branch as one literal string; and
    # `owner: ""  # comment` kept the comment as part of the "empty" value.
    frontmatter = _schema_example_frontmatter()

    fm = _parse_frontmatter(frontmatter)

    assert fm["kind"] == "story"
    assert fm["title"] == "Epic 1 — hello-api"
    assert fm["owned_paths"] == ["src/hello_api/**"]
    assert fm["owner"] == ""
    assert fm["scaffold"] == "python-api"
    assert fm["port"] == "8099"


def test_hash_inside_a_quoted_title_survives_comment_stripping(tmp_path):
    (tmp_path / "e1.md").write_text(
        "---\n"
        'title: "Epic 1 — hello-api #1"  # a real trailing comment\n'
        "epic_n: 1\n"
        "slug: hello-api\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert epics[0]["title"] == "Epic 1 — hello-api #1"


def test_schema_shaped_epic_end_to_end_check_assign_round_trip(tmp_path):
    # The schema's commented shape must survive the WHOLE pipeline, not just
    # the parser: --check PASS, --assign writes the (still-commented) file
    # cleanly, and the result re-parses to the same values plus the new owner.
    frontmatter = _schema_example_frontmatter()
    # The schema's own example ships an UNASSIGNED epic (owner: "") with a
    # non-conforming title for THIS test's epic_n=1 slot -- reuse it verbatim
    # except give it the "Epic 1 — [Name]" shape check a real epic satisfies
    # (the schema's literal example already does: "Epic 1 — hello-api").
    path = tmp_path / "e1.md"
    path.write_text(frontmatter + "\n## Epic 1 — hello-api\n\nBody.\n", encoding="utf-8")

    assert main(["--epics-dir", str(tmp_path), "--check"]) == 0

    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha"]) == 0

    epics = load_epics(str(tmp_path))
    e = epics[0]
    assert e["owner"] == "alpha"
    assert e["owned_paths"] == ["src/hello_api/**"]
    assert e["title"] == "Epic 1 — hello-api"
    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", "alpha"]) == 0


def test_assign_tail_terminator_follows_the_preceding_line_not_file_global(tmp_path):
    # VERIFY (deepseek): the TAIL-append branch picked the inserted line's
    # terminator from a file-global CRLF scan, not from the specific line
    # owner: follows -- a mostly-CRLF frontmatter whose LAST field is bare
    # LF got a CRLF owner: line (and an extra "\r" byte injected right after
    # that LF line that was never in the original file).
    original = (
        "---\r\n"
        "title: Epic 1 — epic-1\r\n"
        "epic_n: 1\r\n"
        "slug: epic-1\r\n"
        "depends_on: []\r\n"
        "parallel_with: []\r\n"
        "owned_paths: []\n"
        "---\r\n"
        "\r\nBody.\r\n"
    )
    path = tmp_path / "e1.md"
    path.write_bytes(original.encode("utf-8"))

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_bytes().decode("utf-8")
    assert text == original.replace("owned_paths: []\n---", "owned_paths: []\nowner: beta\n---")


def test_block_shaped_title_is_a_malformed_finding_not_a_crash(tmp_path):
    # Round 5(H, pool): a block-shaped value under a SCALAR key used to be
    # silently promoted to a LIST -- title becoming a list crashed
    # check_integrity's re.match with TypeError instead of the clean
    # "title != Epic N — [Name]" finding master produced.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title:\n"
        "  - not\n"
        "  - a\n"
        "  - scalar\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert isinstance(epics[0]["title"], str)
    findings = check_integrity(epics, expected_count=None)
    assert any("malformed value for title" in f for f in findings), findings
    assert any("title" in f and "!= " in f for f in findings), findings

    assert main(["--epics-dir", str(tmp_path), "--check"]) == 1
    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", "alpha"]) == 1
    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha"]) == 1


def test_block_shaped_owner_is_a_malformed_finding_not_a_crash(tmp_path):
    # owner becoming a list used to crash `owner not in owners` with
    # TypeError: unhashable type: 'list'.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "owner:\n"
        "  - not\n"
        "  - a\n"
        "  - scalar\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert isinstance(epics[0]["owner"], str)
    findings = check_integrity(epics, expected_count=None)
    assert any("malformed value for owner" in f for f in findings), findings

    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", "alpha"]) == 1
    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha"]) == 1


def test_block_shaped_slug_is_a_malformed_finding_json_envelope_intact(tmp_path):
    # slug becoming a list degraded silently in the phase print; --json must
    # keep its envelope (ok/findings/phases), never a bare traceback.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug:\n"
        "  - not\n"
        "  - a\n"
        "  - scalar\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )

    rc = main(["--epics-dir", str(tmp_path), "--json"])

    assert rc == 1
    epics = load_epics(str(tmp_path))
    assert isinstance(epics[0]["slug"], str)
    findings = check_integrity(epics, expected_count=None)
    assert any("malformed value for slug" in f for f in findings), findings


def test_assign_inserts_after_full_multiline_owned_paths_block(tmp_path):
    # Round 3 finding 2: a multi-line YAML block list ("owned_paths:" then
    # "  - item" continuation lines) must get owner: AFTER the WHOLE block,
    # not between the key and its first item.
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths:\n"
        "  - src/a/**\n"
        "  - src/b/**\n"
        "scaffold: python-api\n"
        "---\n"
        "\nBody.\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    scaffold_idx = next(i for i, line in enumerate(lines) if line.startswith("scaffold:"))
    assert lines[scaffold_idx - 1] == "owner: beta"
    assert lines[scaffold_idx - 2] == "  - src/b/**"
    assert lines[scaffold_idx - 3] == "  - src/a/**"


def test_multiline_owned_paths_parses_as_a_real_list_for_disjointness(tmp_path):
    # The other half of finding 2: the flat parser used to read a multi-line
    # owned_paths as "" -- two PARALLEL epics sharing every path via that ""
    # would never be flagged. Prove the parser now collects the "  - " items,
    # so the pre-existing disjointness check can actually see the overlap.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: [2]\n"
        "owned_paths:\n"
        "  - src/shared/**\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / "e2.md").write_text(
        "---\n"
        "title: Epic 2 — epic-2\n"
        "epic_n: 2\n"
        "slug: epic-2\n"
        "depends_on: []\n"
        "parallel_with: [1]\n"
        "owned_paths:\n"
        "  - src/shared/**\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))
    assert epics[0]["owned_paths"] == ["src/shared/**"]
    findings = check_integrity(epics, expected_count=None)
    assert any("share owned_paths" in f for f in findings), findings


def test_multiline_owned_paths_quoted_item_with_inline_comment(tmp_path):
    # Round 4 finding 1: an inline comment on a quoted item used to mis-strip
    # the quotes -- '"src/a/**"  # core service' became 'src/a/**"  # core
    # service' (leading quote gone, trailing quote+comment kept) -- a corrupt
    # path that would compare garbage in the disjointness/migration checks.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths:\n"
        '  - "src/a/**"  # core service\n'
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert epics[0]["owned_paths"] == ["src/a/**"]


def test_multiline_owned_paths_tolerates_interior_comment_and_blank_line(tmp_path):
    # A comment line and a blank line BETWEEN items must not truncate the
    # list -- the same vacuous-pass shape this parser exists to close.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths:\n"
        "  - src/a/**\n"
        "  # a note about the next path\n"
        "\n"
        "  - src/b/**\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert epics[0]["owned_paths"] == ["src/a/**", "src/b/**"]


def test_multiline_owned_paths_preserves_hash_inside_quoted_value(tmp_path):
    # A "#" INSIDE a quoted value is part of the value, never a comment start.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths:\n"
        '  - "src/a/**#special"\n'
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert epics[0]["owned_paths"] == ["src/a/**#special"]


def test_assign_inserts_after_multiline_owned_paths_with_interior_comment_and_blank(tmp_path):
    # The placement regex must agree with the parser on where the block ends:
    # owner: lands after the LAST item, past any interior comment/blank.
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths:\n"
        "  - src/a/**\n"
        "  # a note\n"
        "\n"
        "  - src/b/**\n"
        "scaffold: python-api\n"
        "---\n"
        "\nBody.\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    scaffold_idx = next(i for i, line in enumerate(lines) if line.startswith("scaffold:"))
    assert lines[scaffold_idx - 1] == "owner: beta"
    assert lines[scaffold_idx - 2] == "  - src/b/**"


def test_assign_multiline_owned_paths_as_last_field_no_blank_line_and_idempotent(tmp_path):
    # Round 4 finding 2: owned_paths' block is the VERY LAST frontmatter
    # field (nothing between it and the closing "---") -- the tail-append
    # branch must not introduce a blank line, and a second run must change
    # no byte.
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths:\n"
        "  - src/a/**\n"
        "  - src/b/**\n"
        "---\n"
        "\nBody.\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_text(encoding="utf-8")
    assert "\n\n---" not in text, "blank line inside the frontmatter before the closing fence"
    lines = text.splitlines()
    fence_idx = lines.index("---", 1)
    assert lines[fence_idx - 1] == "owner: beta"
    assert lines[fence_idx - 2] == "  - src/b/**"

    before = path.read_bytes()
    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0
    assert path.read_bytes() == before


def test_assign_preserves_mixed_terminators_around_insertion(tmp_path):
    # Round 3 finding 3: a file with the owned_paths line in bare LF but
    # everything ELSE in CRLF (a mixed-terminator file) must not have that
    # line's own LF silently rewritten to the file's majority CRLF style --
    # the inserted line gets the SAME terminator as the line it follows.
    original = (
        "---\r\n"
        "title: Epic 1 — epic-1\r\n"
        "epic_n: 1\r\n"
        "slug: epic-1\r\n"
        "depends_on: []\r\n"
        "parallel_with: []\r\n"
        "owned_paths: []\n"
        "scaffold: python-api\r\n"
        "---\r\n"
        "\r\nBody.\r\n"
    )
    path = tmp_path / "e1.md"
    path.write_bytes(original.encode("utf-8"))

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_bytes().decode("utf-8")
    assert text == original.replace(
        "owned_paths: []\nscaffold:", "owned_paths: []\nowner: beta\nscaffold:"
    )


def test_assign_preserves_blank_line_before_closing_fence(tmp_path):
    # Round 3 finding 4: a deliberate blank line right before the closing
    # fence must survive -- the old body.rstrip("\r\n") ate it, treating it
    # the same as "no blank line at all".
    original = (
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "\n"
        "---\n"
        "\nBody.\n"
    )
    path = tmp_path / "e1.md"
    path.write_text(original, encoding="utf-8")

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_text(encoding="utf-8")
    assert text == original.replace("owned_paths: []\n\n---", "owned_paths: []\n\nowner: beta\n---")


def test_assign_on_empty_dir_is_refused_not_a_vacuous_ok(tmp_path, capsys):
    # Round 3 finding 1: the zero-epics guard was armed only for --check
    # --owners; --assign over an empty (or misspelled) --epics-dir wrote
    # nothing and printed ASSIGN: OK with rc 0 regardless.
    rc = main(["--epics-dir", str(tmp_path), "--assign", "alpha,beta"])

    assert rc == 1
    out = capsys.readouterr().out
    assert "no epics found" in out
    assert "ASSIGN: OK" not in out


def test_assign_on_empty_dir_with_expected_count_zero_succeeds(tmp_path, capsys):
    rc = main(["--epics-dir", str(tmp_path), "--assign", "alpha", "--expected-count", "0"])

    assert rc == 0
    assert "ASSIGN: OK" in capsys.readouterr().out


def test_assign_integrity_failure_writes_nothing(tmp_path):
    # epic_n=2 with no epic_n=1 -> non-contiguous numbering -> an integrity finding
    _write_epic(tmp_path / "e2.md", 2)
    before = (tmp_path / "e2.md").read_bytes()

    rc = main(["--epics-dir", str(tmp_path), "--assign", "alpha,beta"])

    assert rc == 1
    assert (tmp_path / "e2.md").read_bytes() == before
    assert _owner_line(tmp_path / "e2.md") is None


def test_assign_rejects_invalid_name_before_any_write(tmp_path):
    # Round 2 finding A: an unvalidated owner name reaches _write_owner's
    # regex-substitution TEMPLATE. `\1` (an invalid group reference) used to
    # crash mid-loop AFTER earlier files were already written, breaking the
    # all-or-nothing contract --help promises; `\g<0>` used to silently
    # duplicate content with rc=0. Every name must be validated before ANY
    # file — including the first phase's "ok" — is touched.
    _write_epic(tmp_path / "e1.md", 1)
    _write_epic(tmp_path / "e2.md", 2, deps="[1]")
    before = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}

    with pytest.raises(SystemExit) as exc_info:
        main(["--epics-dir", str(tmp_path), "--assign", r"ok,\1bad,alsook"])

    assert exc_info.value.code == 2
    after = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}
    assert after == before, "a file was written despite the invalid name"


def test_assign_rejects_group_reference_name_before_any_write(tmp_path):
    # The other half of finding A's example: `\g<0>` doesn't crash — it
    # silently duplicates content with rc=0 if it ever reaches re.sub's
    # replacement template. Same bar: rejected before any write.
    _write_epic(tmp_path / "e1.md", 1)
    before = (tmp_path / "e1.md").read_bytes()

    with pytest.raises(SystemExit) as exc_info:
        main(["--epics-dir", str(tmp_path), "--assign", r"a\g<0>b"])

    assert exc_info.value.code == 2
    assert (tmp_path / "e1.md").read_bytes() == before


def test_owners_rejects_invalid_name(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, owner="alpha")

    with pytest.raises(SystemExit) as exc_info:
        main(["--epics-dir", str(tmp_path), "--check", "--owners", "not valid!"])

    assert exc_info.value.code == 2


@pytest.mark.parametrize("name", ["a", "a" * 32, "alpha", "a1-b2", "x-y-z", "0-9-a"])
def test_assign_then_check_owners_round_trips_for_every_accepted_name_shape(tmp_path, name):
    # Round 2 finding E: writer/reader quoting is closed by finding A's
    # validation (no accepted name can carry a quote) — proved by round-trip.
    _write_epic(tmp_path / "e1.md", 1)

    assert main(["--epics-dir", str(tmp_path), "--assign", name]) == 0
    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", name]) == 0


def test_check_owners_rejects_unknown_owner(tmp_path, capsys):
    _write_epic(tmp_path / "e1.md", 1, owner="delta")

    rc = main(["--epics-dir", str(tmp_path), "--check", "--owners", "alpha,beta,gamma"])

    assert rc == 1
    out = capsys.readouterr().out
    assert "e1.md" in out
    assert "owner" in out and "delta" in out


def test_owners_without_check_is_a_usage_error(tmp_path):
    # --owners silently discarded (findings computed with owners=None) would make
    # `epic_order.py --owners a,b --json` exit 0 while asserting nothing about
    # ownership — the flag only means something paired with --check.
    _write_epic(tmp_path / "e1.md", 1, owner="delta")

    with pytest.raises(SystemExit) as exc_info:
        main(["--epics-dir", str(tmp_path), "--owners", "alpha,beta", "--json"])

    assert exc_info.value.code == 2


def test_check_owners_on_empty_dir_is_not_a_vacuous_pass(tmp_path):
    # Round 2 finding F: an owner gate pointed at an empty/wrong --epics-dir
    # must not silently PASS — there is nothing there to have verified.
    rc = main(["--epics-dir", str(tmp_path), "--check", "--owners", "alpha,beta"])
    assert rc == 1


def test_check_owners_on_empty_dir_with_expected_count_zero_passes(tmp_path):
    # The explicit escape hatch: a genuinely-empty epics dir is asserted, not guessed.
    rc = main(
        ["--epics-dir", str(tmp_path), "--check", "--owners", "alpha,beta", "--expected-count", "0"]
    )
    assert rc == 0


def test_check_without_owners_result_unchanged_from_today(tmp_path):
    # An epic with no owner field at all — plain --check (no --owners) must not
    # care: this is the "unchanged from today" behaviour the ticket pins.
    _write_epic(tmp_path / "e1.md", 1)
    epics = load_epics(str(tmp_path))

    assert check_integrity(epics, expected_count=None) == []
    assert main(["--epics-dir", str(tmp_path), "--check"]) == 0


def test_check_integrity_reports_duplicate_epic_n(tmp_path):
    # Pre-existing behaviour (not added by this ticket) — verified + regression-guarded here.
    _write_epic(tmp_path / "e1.md", 1)
    _write_epic(tmp_path / "e1b.md", 1)

    epics = load_epics(str(tmp_path))
    findings = check_integrity(epics, expected_count=None)

    assert any("duplicate epic numbers" in f and "[1]" in f for f in findings), findings
    assert main(["--epics-dir", str(tmp_path), "--check"]) == 1


def test_check_integrity_reports_duplicate_owner_lines(tmp_path):
    # Round 5 finding 1: a frontmatter carrying TWO owner: lines (hand-edited
    # or previously corrupted) has the writer (updates only the FIRST, via
    # count=1) and the reader (last-wins) disagreeing about which one is
    # real -- flagged unconditionally so --assign refuses before writing.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "owner: first\n"
        "owner: stale-two\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))
    findings = check_integrity(epics, expected_count=None)

    assert any("multiple owner:" in f and "e1.md" in f for f in findings), findings
    # Unconditional: fires on a plain --check too, not just --check --owners.
    assert main(["--epics-dir", str(tmp_path), "--check"]) == 1


def test_assign_refuses_on_duplicate_owner_lines(tmp_path, capsys):
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "owner: first\n"
        "owner: stale-two\n"
        "---\n",
        encoding="utf-8",
    )
    before = (tmp_path / "e1.md").read_bytes()

    rc = main(["--epics-dir", str(tmp_path), "--assign", "alpha"])

    assert rc == 1
    assert "ASSIGN: REFUSED" in capsys.readouterr().out
    assert (tmp_path / "e1.md").read_bytes() == before


def test_assign_refuses_cleanly_on_dependency_cycle(tmp_path, capsys):
    # Round 5 finding 2: a depends_on CYCLE used to escape --assign as an
    # uncaught ValueError traceback from phased_order(). T03b converts the
    # cycle into a check_integrity finding -- out of scope here; this ticket
    # only needs the entry point to catch it and refuse cleanly.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: [2]\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / "e2.md").write_text(
        "---\n"
        "title: Epic 2 — epic-2\n"
        "epic_n: 2\n"
        "slug: epic-2\n"
        "depends_on: [1]\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )
    before = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}

    rc = main(["--epics-dir", str(tmp_path), "--assign", "alpha"])

    assert rc == 1
    out = capsys.readouterr().out
    assert "ASSIGN: REFUSED" in out
    assert "cycle" in out.lower()
    after = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}
    assert after == before


def test_loader_exposes_owner_field(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, owner="alpha")
    epics = load_epics(str(tmp_path))
    assert epics[0]["owner"] == "alpha"


def test_mega_docs_are_free_of_retired_references():
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    checklist = _CHECKLIST_PATH.read_text(encoding="utf-8")
    for token in ("traycer_mirror", "epic-to-ticket-workflow"):
        assert token not in schema, f"{token!r} still present in EPIC-ARTIFACT-SCHEMA.md"
        assert token not in checklist, (
            f"{token!r} still present in EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md"
        )


def test_docs_cockpit_driver_card_mentions_all_state_never_built():
    # Round 2 finding C/D: 84d says the cockpit/driver were never built; every
    # OTHER mention of cockpit/driver/CARD in either doc must say the same,
    # never imply the mechanism runs today. Prose wraps across lines, so a hit
    # is judged against a window of the next few lines, not one bare line.
    pattern = re.compile(r"cockpit|driver|CARD", re.IGNORECASE)
    never_built = re.compile(r"never built|never realized|was ever built", re.IGNORECASE)
    window = 3
    for label, path in (("schema", _SCHEMA_PATH), ("checklist", _CHECKLIST_PATH)):
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, 1):
            if pattern.search(line):
                context = " ".join(lines[lineno - 1 : lineno - 1 + window])
                assert never_built.search(context), (
                    f"{label}:{lineno}: mentions cockpit/driver/CARD without stating "
                    f"it was never built (within {window} lines): {line!r}"
                )


def test_kind_field_has_no_code_reader():
    # Round 2 finding D: `kind` is documented as retained-for-compatibility with
    # no current reader — verified against the actual source, not just the doc.
    # A single-quoted reader ('kind') passed the old double-quote-only check.
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert not re.search(r"""['"]kind['"]""", source)


def test_assign_with_json_is_a_usage_error(tmp_path):
    # Round 3 finding 7: --assign silently discarded --json (rc 0, plain
    # ASSIGN: stdout even though --json was requested).
    _write_epic(tmp_path / "e1.md", 1)

    with pytest.raises(SystemExit) as exc_info:
        main(["--epics-dir", str(tmp_path), "--assign", "alpha", "--json"])

    assert exc_info.value.code == 2


def test_assign_with_check_is_a_usage_error(tmp_path):
    _write_epic(tmp_path / "e1.md", 1)

    with pytest.raises(SystemExit) as exc_info:
        main(["--epics-dir", str(tmp_path), "--assign", "alpha", "--check"])

    assert exc_info.value.code == 2


def test_checklist_item_93_no_longer_cites_traycer_tickets_or_dispatch_instructions():
    # Round 3 finding 6: item 93's parenthetical still said "Traycer tickets"
    # and "dispatch instructions with fixed steps" -- both retired concepts
    # (84f: no command emits dispatch instructions; 84d: no Traycer layer).
    checklist = _CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "Traycer tickets" not in checklist
    assert "dispatch instructions with fixed steps" not in checklist


def test_checklist_has_exactly_one_traycer_mention_the_84d_historical_one():
    checklist = _CHECKLIST_PATH.read_text(encoding="utf-8")
    hits = re.findall(r"traycer", checklist, re.IGNORECASE)
    assert len(hits) == 1, hits


def test_classify_fm_line_basic_shapes():
    # The structural fix: ONE classifier, used by both the parser's block
    # collector and the writer's placement/replacement.
    assert _classify_fm_line("---") == ("fence",)
    assert _classify_fm_line("   ") == ("blank",)
    assert _classify_fm_line("") == ("blank",)
    assert _classify_fm_line("  # a comment") == ("comment",)
    assert _classify_fm_line("# a comment") == ("comment",)
    assert _classify_fm_line("  - src/a/**") == ("item", "src/a/**")
    assert _classify_fm_line("owner: alpha") == ("key", "owner", "alpha")
    assert _classify_fm_line("owner : alpha") == ("key", "owner", "alpha")
    assert _classify_fm_line("  owner: alpha") == ("key", "owner", "alpha")
    assert _classify_fm_line("no colon here") == ("other",)


def test_multiline_owned_paths_tolerates_whitespace_only_interior_line(tmp_path):
    # Round 6 finding 1: a WHITESPACE-ONLY interior line ("   ", not
    # byte-empty) inside a block used to be skipped by the parser
    # (`not raw.strip()`) but NOT by the placement regex's
    # `(?=\r?\n|$)`, which needed a truly empty line -- owner: landed
    # INSIDE the block and an item was lost. The classifier answers
    # "blank?" identically for both consumers now.
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths:\n"
        "  - src/a/**\n"
        "   \n"
        "  - src/b/**\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))
    assert epics[0]["owned_paths"] == ["src/a/**", "src/b/**"]

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    owner_idx = lines.index("owner: beta")
    assert lines[owner_idx - 1] == "  - src/b/**"

    epics2 = load_epics(str(tmp_path))
    assert epics2[0]["owned_paths"] == ["src/a/**", "src/b/**"]
    assert epics2[0]["owner"] == "beta"


def test_owner_with_space_before_colon_replaced_in_place_not_duplicated(tmp_path):
    # Round 6 finding 2: `_OWNER_LINE_RE = ^owner:` did not match `owner :
    # alpha` (a space before the colon) even though the parser's
    # `key.strip()` reads the key fine -- --assign wrote a SECOND owner:
    # line at rc 0, and the next --check refused on the resulting
    # duplicate (idempotency broken; _dup_owner cannot fire pre-write).
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "owner : old\n"
        "---\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    owner_like = [line for line in lines if line.split(":", 1)[0].strip() == "owner"]
    assert owner_like == ["owner: beta"], owner_like

    before = path.read_bytes()
    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0
    assert path.read_bytes() == before

    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", "beta"]) == 0


def test_indented_owner_line_replaced_in_place_not_duplicated(tmp_path):
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "  owner: old\n"
        "---\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    owner_like = [line for line in lines if line.split(":", 1)[0].strip() == "owner"]
    assert owner_like == ["owner: beta"], owner_like
    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", "beta"]) == 0


def test_apostrophe_in_unquoted_value_does_not_trap_the_comment_scanner(tmp_path):
    # Round 6 finding 3: _strip_unquoted_comment treated an apostrophe
    # ANYWHERE in an unquoted value as an opening quote, so the trailing
    # comment survived. A quote only opens a quoted value at position 0.
    (tmp_path / "e1.md").write_text(
        "---\n"
        "title: Epic 1 — Bob's API  # a trailing comment\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert epics[0]["title"] == "Epic 1 — Bob's API"


def test_double_quoted_value_with_apostrophe_still_correct(tmp_path):
    title_line = 'title: "Epic 1 \u2014 Bob\'s API"  # a trailing comment\n'
    (tmp_path / "e1.md").write_text(
        "---\n" + title_line + "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )

    epics = load_epics(str(tmp_path))

    assert epics[0]["title"] == "Epic 1 \u2014 Bob's API"


def test_existing_owner_line_replacement_discards_its_trailing_comment(tmp_path):
    # Round 6 finding 4: the docstring now states the truth -- replacement
    # is a WHOLE-LINE swap, so a comment on the old owner: line is
    # discarded, never preserved.
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "owner: old  # keep me?\n"
        "---\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_text(encoding="utf-8")
    assert "owner: beta\n" in text
    assert "keep me" not in text


def test_assign_help_text_names_check_owners_grade_integrity(capsys):
    # Round 6 finding 5: --assign's help said it "refuses when --check
    # would report any finding" -- but --assign passes require_epics=True
    # and plain --check does not, so the empty-dir refusal is
    # --owners-grade behaviour, not plain --check's.
    with pytest.raises(SystemExit):
        main(["--help"])

    out = capsys.readouterr().out
    normalized = " ".join(out.split())  # argparse wraps help text across lines
    assert "empty-dir refusal" in normalized


def test_exactly_one_compiled_regex_and_none_mentions_owner_fields():
    # Round 7 finding 3: a NAME guard ("_OWNER_LINE_RE"/"_OWNED_PATHS_BLOCK_RE"
    # not in source) is defeated by a second regex under any OTHER name --
    # proven live: adding `_OWNER_KEY_RE = re.compile(...)` and
    # `_OWNED_PATHS_RE = re.compile(...)` back in left the old guard green.
    # A PROPERTY assertion instead: exactly one `re.compile(` call survives
    # in the whole module (the agent-name validator), and no compiled
    # pattern's TEXT mentions "owner" or "owned_paths" -- so a second regex
    # cannot reappear under ANY name without going red here.
    source = _SCRIPT_PATH.read_text(encoding="utf-8")

    assert source.count("re.compile(") == 1, (
        f"expected exactly one re.compile(...) call, found {source.count('re.compile(')}"
    )

    patterns = re.findall(r're\.compile\(\s*r?"([^"]*)"', source)
    assert patterns, "no compiled regex pattern found to inspect"
    for pattern in patterns:
        assert "owner" not in pattern.lower()
        assert "owned_paths" not in pattern.lower()


def test_malformed_opening_fence_four_dashes_refused_by_both(tmp_path):
    # Round 7 finding 1a: `text.startswith("---")` accepted "----" (four
    # dashes) as a PREFIX match for the opening fence, so --check PASSed
    # and --assign wrote nothing while claiming ASSIGN: OK -- the ":419
    # comment" ("load_epics already flags this file") was false, because
    # load_epics never flagged it. _find_fences requires the whole trimmed
    # line to equal "---", so "----" opens no frontmatter at all -- for
    # BOTH consumers -- and load_epics genuinely does flag it now.
    path = tmp_path / "e1.md"
    path.write_text(
        "----\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "owned_paths: []\n"
        "---\n",
        encoding="utf-8",
    )
    before = path.read_bytes()

    assert main(["--epics-dir", str(tmp_path), "--check"]) == 1
    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha"]) == 1
    assert path.read_bytes() == before

    epics = load_epics(str(tmp_path))
    assert epics[0].get("_no_frontmatter") is True


def test_indented_triple_dash_interior_line_is_not_a_fence_for_either_side(tmp_path):
    # Round 7 finding 1b: the writer's classifier (raw.strip() == "---")
    # tolerated indentation and stopped at "  ---", while the parser's
    # `text.find("\n---", 3)` required column 0 and read past it -- the
    # writer inserted owner: at its (wrong) early boundary while the parser
    # kept reading the REAL frontmatter further down, producing a second
    # owner: line and a --check --owners refusal forever after. Fence
    # detection now requires NO leading whitespace (rstrip-only), so
    # "  ---" is ordinary content to both sides -- the real closing fence
    # is what both agree on. owned_paths sits AFTER "  ---" with a
    # non-default value so a swallowed field is directly observable (an
    # empty-default coincidentally matching [] would hide the bug).
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "  ---\n"
        'owned_paths: ["src/a/**"]\n'
        "scaffold: python-api\n"
        "---\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--check"]) == 0
    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha"]) == 0
    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", "alpha"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    owner_like = [line for line in lines if line.split(":", 1)[0].strip() == "owner"]
    assert owner_like == ["owner: alpha"], owner_like

    epics = load_epics(str(tmp_path))
    assert epics[0]["owned_paths"] == ["src/a/**"]


def test_interior_fence_like_line_with_trailing_text_is_not_a_fence_for_either_side(tmp_path):
    # Round 7 finding 1c: an interior "--- separator note" line closed the
    # OLD parser's frontmatter early (a bare prefix match) while the
    # writer's classifier (exact "---" only) read past it to the real
    # close -- --assign wrote below the parser's (wrong) boundary and
    # --check --owners failed forever, since the parser never even saw the
    # written owner: line as part of the frontmatter.
    #
    # Round 8 finding 1: a mutant where _write_owner bypasses _find_fences
    # and scans for fences ITSELF (by prefix) passed all 64 tests -- the
    # distinguishing fixture needs a PRE-EXISTING owner: line AFTER the
    # fence-lookalike (and after owned_paths:) so a writer using its OWN
    # early boundary never sees it and inserts a SECOND owner: line
    # instead of replacing the first (mutant G: two owner: lines,
    # --check rc 1 "multiple owner: lines", the next --assign REFUSED).
    path = tmp_path / "e1.md"
    path.write_text(
        "---\n"
        "title: Epic 1 — epic-1\n"
        "epic_n: 1\n"
        "slug: epic-1\n"
        "depends_on: []\n"
        "parallel_with: []\n"
        "--- separator note\n"
        'owned_paths: ["src/a/**"]\n'
        "owner: old\n"
        "scaffold: python-api\n"
        "---\n",
        encoding="utf-8",
    )

    assert main(["--epics-dir", str(tmp_path), "--check"]) == 0
    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha"]) == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    owner_like = [line for line in lines if line.split(":", 1)[0].strip() == "owner"]
    assert owner_like == ["owner: alpha"], owner_like

    assert main(["--epics-dir", str(tmp_path), "--check", "--owners", "alpha"]) == 0

    # Idempotent re-assign: still exactly one owner: line, unchanged value.
    assert main(["--epics-dir", str(tmp_path), "--assign", "alpha"]) == 0
    lines2 = path.read_text(encoding="utf-8").splitlines()
    owner_like2 = [line for line in lines2 if line.split(":", 1)[0].strip() == "owner"]
    assert owner_like2 == ["owner: alpha"], owner_like2

    epics = load_epics(str(tmp_path))
    assert epics[0]["owned_paths"] == ["src/a/**"]


def test_form_feed_terminator_round_trips_without_destroying_data(tmp_path):
    # Round 7 finding 2: _line_terminator only recognized \r\n/\r/\n, while
    # str.splitlines() (used by both consumers to cut lines in the first
    # place) splits on the FULL boundary set too -- a line ending in "\x0c"
    # (form feed) read as terminator-less to _line_terminator, so the
    # writer's replacement glued the new owner: line directly onto the
    # NEXT physical line with no separator: "owner: betaowned_paths: []"
    # -- DATA DESTROYED at rc 0, even though rc 0 claimed success.
    path = tmp_path / "e1.md"
    path.write_bytes(
        (
            "---\n"
            "title: Epic 1 — epic-1\n"
            "epic_n: 1\n"
            "slug: epic-1\n"
            "depends_on: []\n"
            "parallel_with: []\n"
            "owner: old\x0c"
            "owned_paths: []\n"
            "---\n"
        ).encode()
    )

    assert main(["--epics-dir", str(tmp_path), "--assign", "beta"]) == 0

    text = path.read_text(encoding="utf-8")
    assert "betaowned_paths" not in text, "owner: and owned_paths: lines got glued together"

    epics = load_epics(str(tmp_path))
    assert epics[0]["owner"] == "beta"
    assert epics[0]["owned_paths"] == []
