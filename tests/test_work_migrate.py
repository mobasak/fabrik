"""Behavior contract for `migrate-backlog` and `render` (ticket T03) — spec § The backlog becomes
a view, § Validation V2; T03 review pass 1 (Decisions R, M, B, T).

`migrate-backlog` turns every ROW of `docs/STRATEGIC_BACKLOG.md` into a `kind: backlog` item;
`render` regenerates the file's `AUTO-GENERATED:BACKLOG` block from the store. Every test runs
against a throwaway git repo under `tmp_path` with an explicit `env=` — never the hub's own
`.fabrik/work/`. The V2 test reads a COPY of this worktree's own `docs/STRATEGIC_BACKLOG.md` (the
same content as the hub file, since both check out the same git history) into its tmp dir; it is
never written.

Decision R (review pass 1): a ROW starts only at a column-0 line of one of six shapes — a `## `
heading (any); a `### ` heading that carries a tag or a resolved marker; a bullet whose content
begins with a bracket tag (bold or not); a checkbox bullet `- [ ]`/`- [x]` (`* ` counts
identically); a bullet whose content begins with `~~`; a table row under a header with a Tag/Owner
cell. Everything else is BODY of the row above.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
HUB_BACKLOG = REPO / "docs" / "STRATEGIC_BACKLOG.md"


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _repo(tmp_path: Path, env: dict[str, str]) -> Path:
    tree = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(tree))
    (tree / "README").write_text("seed\n", encoding="utf-8")
    _git(tree, env, "add", "README")
    _git(tree, env, "commit", "-q", "-m", "seed")
    return tree.resolve()


def run(
    args: list[str], env: dict[str, str], cwd: Path, timeout: float = 120
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _ok(args: list[str], env: dict[str, str], cwd: Path) -> str:
    r = run(args, env, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _store(tmp_path: Path, env: dict[str, str], distributor: str = "intel") -> Path:
    repo = _repo(tmp_path, env)
    _ok(["init", "--distributor", distributor], env, repo)
    return repo


def _backlog(repo: Path, text: str) -> Path:
    p = repo / "docs" / "STRATEGIC_BACKLOG.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _items(repo: Path) -> list[dict]:
    store = repo / ".fabrik" / "work"
    if not store.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(store.glob("W-*.json"))]


def _backlog_items(repo: Path) -> list[dict]:
    return [it for it in _items(repo) if it.get("kind") == "backlog"]


def _config(repo: Path) -> dict:
    return json.loads((repo / ".fabrik" / "work" / "config.json").read_text(encoding="utf-8"))


# ── fixture backlog: one row of every Decision-R shape, open and resolved ───────────────────────

FIXTURE = """# Strategic Backlog

Intro paragraph.

---

## [infra] Heading row open (2026-09-23)
A paragraph of body text under the heading.
A second line of body text.

### Untagged narrative sub-header, no tag or resolved marker at all
This sub-header and its prose are BODY of the heading above, not a row of their own.

## [fleet] Heading row LANDED 2026-09-18 already

### [operator] Tagged sub-header is its own row (2026-09-24)
body of the tagged sub-header

- **[infra] Open bullet row (2026-09-23)** — some descriptive text.
  a continuation line, absorbed as body of this bullet
- a plain untagged bullet with no tag, no checkbox, no strike — becomes body of the row above
- [ ] **[infra]** **Checkbox open bullet, bold tag then bold title (2026-09-09)** — text.
- [x] **[infra]** **SHIPPED 2026-09-10 checkbox-resolved bullet** — text.
- ~~**[operator] Struck resolved bullet (2026-09-20)**~~ ✅ **RESOLVED 2026-09-23 (D-360)** — text.
* **[fleet] star bullet counts like dash (2026-09-01)** — text.

## untagged heading with no tag at all (2026-09-24)
a row-start shape that fails to parse still becomes an item, per contract row 2

| Tag | Agent | Beat |
| :--- | :--- | :--- |
| `[infra]` | infra | the legend table — never migrated |

| Effort | Owner | Item | Why | Ready |
| :--- | :--- | :--- | :--- | :--- |
| ~~**M**~~ | `[infra]` | ~~**Resolved table row**~~ ✅ **SHIPPED 2026-06-08** | why | n/a |
| **M** | `[fleet]` | **Open table row** | why | when |
"""
# Rows (11, the legend table excluded): 3 heading2 (infra open, fleet resolved, untagged open),
# 1 tagged heading3, 5 bullets (open, plain-untagged excluded as body, checkbox-open,
# checkbox-resolved, struck-resolved, star), 2 table rows (resolved, open).


def test_migrate_backlog_turns_every_row_into_exactly_one_item(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, FIXTURE)
    out = _ok(["migrate-backlog"], env, repo)
    items = _backlog_items(repo)

    assert "11 item(s) created" in out
    assert len(items) == 11, [it["title"] for it in items]

    by_owner_open = {it["owner"] for it in items if it["status"] == "open"}
    by_owner_done = {it["owner"] for it in items if it["status"] == "done"}
    assert {"infra", "fleet", "operator"} <= by_owner_open
    assert "" in by_owner_open  # the untagged heading, contract row 2's fallback
    assert {"infra", "operator", "fleet"} <= by_owner_done

    resolved_titles = {it["title"] for it in items if it["status"] == "done"}
    assert any("SHIPPED 2026-09-10" in t for t in resolved_titles)
    assert any("Struck resolved bullet" in t for t in resolved_titles)
    assert any("LANDED 2026-09-18" in t for t in resolved_titles)
    assert any("Resolved table row" in t for t in resolved_titles)

    for it in items:
        assert it["legacy"] is (it["status"] == "done")

    # Decision R: body absorbs the untagged ### sub-header, prose, and the plain untagged bullet
    heading_item = next(it for it in items if "Heading row open" in it["title"])
    assert "A paragraph of body text under the heading." in heading_item["next"]
    assert "A second line of body text." in heading_item["next"]
    assert "Untagged narrative sub-header" in heading_item["next"]
    assert "This sub-header and its prose are BODY" in heading_item["next"]

    bullet_item = next(it for it in items if "Open bullet row" in it["title"])
    assert "a continuation line, absorbed as body of this bullet" in bullet_item["next"]
    assert "a plain untagged bullet with no tag" in bullet_item["next"]


def test_a_row_start_that_fails_to_parse_gets_an_empty_owner_and_is_listed(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, FIXTURE)
    out = _ok(["migrate-backlog"], env, repo)
    items = _backlog_items(repo)
    untagged = next(it for it in items if "untagged heading with no tag at all" in it["title"])
    assert untagged["owner"] == ""
    assert untagged["status"] == "open"
    assert "a row-start shape that fails to parse" in untagged["next"]
    assert untagged["id"] in out  # listed for the distributor


def test_migrate_backlog_run_again_creates_nothing(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, FIXTURE)
    _ok(["migrate-backlog"], env, repo)
    before = {it["id"]: it for it in _items(repo)}
    out = _ok(["migrate-backlog"], env, repo)
    after = {it["id"]: it for it in _items(repo)}
    assert before == after
    assert "0 item(s) created" in out


def test_migrate_backlog_records_migrated_at_once_and_only_once(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, FIXTURE)
    assert "migrated_at" not in _config(repo)
    _ok(["migrate-backlog"], env, repo)
    first = _config(repo)["migrated_at"]
    assert first
    _ok(["migrate-backlog"], env, repo)
    assert _config(repo)["migrated_at"] == first


def test_migrate_backlog_on_a_missing_file_creates_nothing(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    assert "migrated_at" not in _config(repo)
    out = _ok(["migrate-backlog"], env, repo)
    assert _items(repo) == []
    assert "no" in out.lower()
    # T09 review A-O5: an empty migration (no backlog file at all) still COMPLETES — otherwise
    # `sync --check` can never become blocking in a repo that never had a backlog to migrate
    first = _config(repo)["migrated_at"]
    assert first
    _ok(["migrate-backlog"], env, repo)
    assert _config(repo)["migrated_at"] == first


def test_migrate_backlog_refuses_without_a_store(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _backlog(repo, FIXTURE)
    r = run(["migrate-backlog"], env, repo)
    assert r.returncode != 0
    assert "init" in r.stderr
    assert not (repo / ".fabrik").exists()


# ── Decision R.7 (A-O3): duplicate source rows are two items, not one ───────────────────────────

DUPLICATE_FIXTURE = """# Strategic Backlog

---

## [infra] Duplicate finding, worded identically both times (2026-09-24)
The exact same body text appears twice in this file, at two different rows.

## [infra] Duplicate finding, worded identically both times (2026-09-24)
The exact same body text appears twice in this file, at two different rows.

## [fleet] A distinct third row (2026-09-24)
distinct body
"""


def test_two_source_rows_with_identical_text_become_two_items(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, DUPLICATE_FIXTURE)
    out = _ok(["migrate-backlog"], env, repo)
    items = _backlog_items(repo)
    assert len(items) == 3, [it["title"] for it in items]
    assert "3 item(s) created" in out
    dup_items = [it for it in items if "Duplicate finding" in it["title"]]
    assert len(dup_items) == 2
    assert dup_items[0]["id"] != dup_items[1]["id"]
    # a second run against the SAME (unchanged) duplicate pair still creates nothing further —
    # dedup is against the store's existing digests, not re-derived from within-run duplicates
    before = len(_backlog_items(repo))
    _ok(["migrate-backlog"], env, repo)
    assert len(_backlog_items(repo)) == before


# ── bandit B324: the row digest declares usedforsecurity=False, output must be unchanged ─────────


def test_row_digest_pins_its_output_for_a_fixed_input():
    work = _work_module()
    text = "a fixed known text for the digest pin"
    assert work._row_digest(text, 0) == "a3b09371c1d1"
    assert work._row_digest(text, 1) == "ae1a4ede95dd"
    # usedforsecurity=False must never change which digest a given (text, ordinal) produces —
    # it only silences the FIPS/security linter (bandit B324), never the hash algorithm or value
    assert work._row_digest(text, 0) != work._row_digest(text, 1)
    # real backlog rows are non-ASCII; the pin must cover the text ENCODING too, not just the
    # hash function — a `.encode()` swapped to latin-1 (or any non-UTF-8) still passes the two
    # ASCII assertions above but changes this one
    assert work._row_digest("ümlaut ✓ 中文", 0) == "5f4b7c576389"


# ── Decision B.3/A-O5: migrate strips render's own block with its exact whitespace ───────────────

WHITESPACE_FIXTURE = """# Strategic Backlog

---

## [infra] A row whose body runs up to where render will insert (2026-09-01)
"""


def test_migrate_render_migrate_creates_nothing_even_when_the_hr_sits_in_a_rows_body(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, WHITESPACE_FIXTURE)
    _ok(["migrate-backlog"], env, repo)
    before = {it["id"]: it["next"] for it in _backlog_items(repo)}
    _ok(["render"], env, repo)
    out = _ok(["migrate-backlog"], env, repo)
    after = {it["id"]: it["next"] for it in _backlog_items(repo)}
    assert before == after
    assert "0 item(s) created" in out


# ── render ───────────────────────────────────────────────────────────────────────────────────


def test_render_inserts_markers_below_the_header_hr_and_lists_open_items(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, FIXTURE)
    _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)
    text = (repo / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
    assert "<!-- AUTO-GENERATED:BACKLOG:START -->" in text
    assert "<!-- AUTO-GENERATED:BACKLOG:END -->" in text
    assert text.index("---") < text.index("<!-- AUTO-GENERATED:BACKLOG:START -->")
    assert "Intro paragraph." in text  # hand-written header text untouched
    open_items = [it for it in _backlog_items(repo) if it["status"] == "open"]
    for it in open_items:
        assert f"(`{it['id']}`)" in text
    done_items = [it for it in _backlog_items(repo) if it["status"] == "done"]
    for it in done_items:
        assert it["id"] not in text


def test_render_never_embeds_a_timestamp(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, FIXTURE)
    _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)
    text = (repo / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
    assert re.search(r"AUTO-GENERATED:BACKLOG v1[^\n]*\|", text) is None
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text[text.index("START") :])


def test_two_fresh_repos_render_byte_identical_blocks(tmp_path, tmp_path_factory):
    other = tmp_path_factory.mktemp("other")
    for base in (tmp_path, other):
        env = _env(base)
        repo = _store(base, env)
        _backlog(repo, "## [infra] T (2026-09-24)\n")
        _ok(["migrate-backlog"], env, repo)
        _ok(["render"], env, repo)
    text_a = (_repo_backlog_path(tmp_path)).read_text(encoding="utf-8")
    text_b = (_repo_backlog_path(other)).read_text(encoding="utf-8")
    block_a = text_a[text_a.index("<!-- AUTO-GENERATED:BACKLOG:START -->") :]
    block_b = text_b[text_b.index("<!-- AUTO-GENERATED:BACKLOG:START -->") :]
    # ids are randomly minted per store (by design — never a claim of THIS test), so compare the
    # block with each store's own id blanked out; what must be identical is everything else,
    # in particular that NEITHER copy carries a wall-clock stamp anywhere (A-H1).
    norm_a = re.sub(r"`W-[0-9a-f]{8}`", "`W-x`", block_a)
    norm_b = re.sub(r"`W-[0-9a-f]{8}`", "`W-x`", block_b)
    assert norm_a == norm_b


def _repo_backlog_path(base: Path) -> Path:
    return base / "repo" / "docs" / "STRATEGIC_BACKLOG.md"


def test_render_run_again_is_byte_identical_and_preserves_surrounding_text(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, FIXTURE)
    _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)
    path = repo / "docs" / "STRATEGIC_BACKLOG.md"
    before = path.read_bytes()
    out = _ok(["render"], env, repo)
    after = path.read_bytes()
    assert before == after
    assert "already current" in out


def test_render_with_no_backlog_file_is_a_noop(tmp_path):
    """T09 review A-O5: T10's adoption runs `init` -> `migrate-backlog` -> `render` in every repo,
    including backlog-less template repos that "migrate to an empty store" — render must exit
    clean there, and it must never CREATE the backlog file (that is never render's job)."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    out = _ok(["render"], env, repo)
    assert "STRATEGIC_BACKLOG.md" in out
    assert not (repo / "docs" / "STRATEGIC_BACKLOG.md").exists()
    assert not (repo / "docs").exists()


# ── T03 review pass 2: Decision M tightened (A-S3, A-O17, A-O18, A-O19) ──────────────────────────


def test_a_checkmark_mentioned_mid_sentence_stays_open(tmp_path):
    """A-S3: a ✅ must sit in a STATUS POSITION (same rule as the uppercase words), not merely
    appear anywhere — a title discussing "the ✅ row" is not itself resolved."""
    work = _work_module()
    rows = work._scan_backlog_rows("## [infra] the right key is git-derived, not the ✅ row\n")
    assert rows[0]["resolved"] is False
    assert rows[0]["owner"] == "infra"


def test_negated_status_words_stay_open(tmp_path):
    """A-O17: \\b word boundaries — RESOLVED must not fire inside UNRESOLVED, nor DONE inside
    UNDONE."""
    work = _work_module()
    assert work._scan_backlog_rows("## [infra] UNRESOLVED 2026-09-20 flake\n")[0]["resolved"] is (
        False
    )
    assert work._scan_backlog_rows("## UNDONE: [infra] rework\n")[0]["resolved"] is False


def test_a_struck_table_item_cell_resolves(tmp_path):
    """A-O18: a table row runs through the SAME resolved rule as any other row — a struck Item
    cell counts as resolved."""
    work = _work_module()
    rows = work._scan_backlog_rows(
        "| Effort | Owner | Item |\n|---|---|---|\n| S | infra | ~~Old item~~ superseded |\n"
    )
    assert rows[0]["resolved"] is True


def test_partial_and_stays_open_negate_a_status_word(tmp_path):
    """A-O19: a status word preceded by PARTIALLY/PARTLY, or a title also saying "stays open"
    (etc.), is NOT resolved — the two real hub titles quoted in the review."""
    work = _work_module()
    rows = work._scan_backlog_rows(
        "## [fleet] RESOLVED for memory (2026-09-05) — the redis-main "
        "EVICTION-POLICY half stays open\n"
    )
    assert rows[0]["resolved"] is False

    rows = work._scan_backlog_rows(
        "- **[infra]** **Store-terminal adjudication** — **PARTIALLY CLOSED "
        "2026-08-25 — the analogue stays blocked.**\n"
    )
    assert rows[0]["resolved"] is False


# ── T03 review pass 2: titles and render (A-O16, A-O20) ──────────────────────────────────────────


def test_title_never_leaves_an_empty_bold_wrapper_or_a_stray_leading_gap(tmp_path):
    """A-O16: removing the tag must remove its OWN isolated bold wrapper too, and collapse a
    leading bold-open left touching a stray space — 124 of 325 real hub titles hit this."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(
        repo,
        "---\n\n## H\n\n- **[infra]** **Store-terminal adjudication** more text here\n",
    )
    _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)
    text = (repo / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
    assert "****" not in text
    assert "- **[infra]** **Store-terminal adjudication** more text here (`" in text
    item = _backlog_items(repo)[0]
    assert not item["title"].startswith("****")
    assert not item["title"].startswith("** ")


def test_hub_copy_titles_never_start_with_an_empty_or_gapped_bold_marker(tmp_path):
    """A-O16 hub-copy assertion: none of the 325 real titles starts with `****` or `** `."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, HUB_BACKLOG.read_text(encoding="utf-8"))
    _ok(["migrate-backlog"], env, repo)
    items = _backlog_items(repo)
    bad = [it["title"] for it in items if it["title"].startswith(("****", "** "))]
    assert bad == []


def test_render_preserves_the_files_crlf_newline_style(tmp_path):
    """A-O20: render reads/writes the file's own newline style — a CRLF fixture's CRLF count is
    unchanged apart from whatever the rendered block itself contributes."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    path = repo / "docs" / "STRATEGIC_BACKLOG.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    crlf_text = "# T\r\n\r\nIntro paragraph.\r\n\r\n---\r\n\r\n## [infra] A thing (2026-09-24)\r\n"
    path.write_bytes(crlf_text.encode("utf-8"))
    before_crlf = path.read_bytes().count(b"\r\n")
    _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)
    raw = path.read_bytes()
    assert b"\r\n" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n")  # every LF is part of a CRLF pair — no bare LF
    # the original 7 CRLF-terminated lines are all still present, verbatim
    assert before_crlf <= raw.count(b"\r\n")
    assert b"Intro paragraph.\r\n" in raw
    assert b"# T\r\n" in raw


def test_a_spaced_cross_tag_resolves_to_its_first_owner(tmp_path):
    """A-O21: `[infra + fleet]` (spaces around the separator) must still resolve to owner
    `infra` — work.py's own fallback, docs_updater.py's regex untouched."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, "---\n\n## [infra + fleet] Eight findings routed (2026-09-24)\nbody\n")
    _ok(["migrate-backlog"], env, repo)
    items = _backlog_items(repo)
    assert len(items) == 1
    assert items[0]["owner"] == "infra"
    assert items[0]["note"].startswith("full-tag:[infra + fleet];") or (
        "full-tag:[infra + fleet]" in items[0]["note"]
    )


# ── T03 review pass 3 (6 confirmed defects in pass 2's own fixes) ───────────────────────────────


def test_a_spaced_cross_tag_never_swallows_a_date_head_or_a_bare_checkbox_letter(tmp_path):
    """A-O22: `_CROSS_TAG_SPACED_RE` needs the SAME guards docs_updater's regex has — a leading
    date bracket (`[2026-09-20 → 2026-09-22]`) or a bare `x`/`+`/`y` checkbox-shaped head must
    never be read as an owner, so the scanner keeps searching and finds the REAL tag past it."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(
        repo,
        "---\n\n"
        "## [2026-09-20 → 2026-09-22] [infra] Sprint window (2026-09-24)\nbody\n\n"
        "## [x + y] [fleet] Checkbox-shaped head (2026-09-24)\nbody\n",
    )
    _ok(["migrate-backlog"], env, repo)
    items = _backlog_items(repo)
    owners = {it["owner"] for it in items}
    assert owners == {"infra", "fleet"}, owners


def test_title_cleanup_never_touches_content_away_from_the_splice_point(tmp_path):
    """A-O23: the `****`/leading-gap cleanup in `_title_without_tag` must act ONLY at the splice
    boundary — an unrelated code span or prose emphasis elsewhere in the row must survive intact."""
    work = _work_module()
    du = work._docs_updater()

    def title_of(text: str) -> str:
        tag = work._find_first_tag(text, du)
        span = tag[2] if tag else None
        return work._title_without_tag(text, span)

    assert title_of("**[infra]** `x****y` z") == "`x****y` z"
    assert title_of("a ****b**** c [infra] d") == "a ****b**** c  d"
    assert "****" not in title_of("**[infra] ** Title")


def test_render_never_flips_a_mostly_lf_file_to_crlf_over_one_stray_line(tmp_path):
    """A-O24: `render` must choose CRLF only when EVERY newline in the file is CRLF — a single
    stray CRLF line elsewhere must never flip the whole file; only the block itself is new
    content, and everything else passes through byte-for-byte."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    path = repo / "docs" / "STRATEGIC_BACKLOG.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "# B\n\nprose line\r\n<!-- AUTO-GENERATED:BACKLOG:START -->\nold\n"
        "<!-- AUTO-GENERATED:BACKLOG:END -->\n\ntail\n"
    )
    path.write_bytes(content.encode("utf-8"))
    before = path.read_bytes()
    assert before.count(b"\r\n") == 1
    _ok(["render"], env, repo)
    after = path.read_bytes()
    assert after.count(b"\r\n") == 1  # unchanged -- never flipped to whole-file CRLF
    assert b"prose line\r\n" in after  # the original stray CRLF line survives, untouched
    assert b"tail\n" in after and b"tail\r\n" not in after  # the LF tail stays LF


def test_a_table_cells_own_leading_or_trailing_checkmark_resolves(tmp_path):
    """A-O25: a match sitting as the FIRST TOKEN of ANY table cell is a status position too, not
    only the Item cell — `| infra | Old item | ✅ |` and `| infra | ✅ Old item |` both resolve."""
    work = _work_module()
    assert work._row_is_resolved("| infra | Old item | ✅ |", is_table=True) is True
    assert work._row_is_resolved("| infra | ✅ Old item |", is_table=True) is True


def test_a_past_tense_stays_open_never_overrides_a_dated_resolution(tmp_path):
    """A-O26: "stays/still/remains open" negates only when it FOLLOWS the matched status word and
    is not itself past tense — "was still open at the 09-19 reading" describes history and must
    not cancel a dated ✅ RESOLVED that precedes it."""
    work = _work_module()
    du = work._docs_updater()
    content = (
        "[infra] ✅ RESOLVED 2026-09-21 (D-400) — the item that was still open at the 09-19 reading"
    )
    tag = work._find_first_tag(content, du)
    assert work._row_is_resolved(content, strike_content=content, tag_span=tag[2]) is True


def test_negations_tolerate_hyphens_and_the_word_not(tmp_path):
    """A-O27: PARTIALLY/PARTLY and stays/still/remains-open negations must be hyphen- and
    whitespace-tolerant (`PARTIALLY-CLOSED`, `still-open`), and NOT is a negation too."""
    work = _work_module()
    du = work._docs_updater()

    def resolved(text: str) -> bool:
        tag = work._find_first_tag(text, du)
        span = tag[2] if tag else None
        return work._row_is_resolved(text, strike_content=text, tag_span=span)

    assert resolved("[infra] foo — PARTIALLY-CLOSED 2026-09-20") is False
    assert resolved("[infra] foo — CLOSED; half still-open") is False
    assert resolved("[infra] NOT DONE 2026-09-20 foo") is False


def test_a_line_merely_quoting_the_start_marker_is_never_treated_as_the_block(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(
        repo,
        "# H\n\nThe view lives in the `<!-- AUTO-GENERATED:BACKLOG:START -->` block.\n\n---\n",
    )
    _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)
    text = (repo / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
    assert "The view lives in the `<!-- AUTO-GENERATED:BACKLOG:START -->` block." in text
    # render again must not corrupt the hand-written line either
    before = text
    _ok(["render"], env, repo)
    after = (repo / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
    assert before == after


def test_two_start_markers_refuse_loudly_and_write_nothing(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    text = (
        "# H\n\n---\n"
        "<!-- AUTO-GENERATED:BACKLOG:START -->\nx\n<!-- AUTO-GENERATED:BACKLOG:END -->\n"
        "<!-- AUTO-GENERATED:BACKLOG:START -->\ny\n<!-- AUTO-GENERATED:BACKLOG:END -->\n"
    )
    _backlog(repo, text)
    before = (repo / "docs" / "STRATEGIC_BACKLOG.md").read_bytes()
    r = run(["render"], env, repo)
    assert r.returncode != 0
    assert "START" in r.stderr
    assert (repo / "docs" / "STRATEGIC_BACKLOG.md").read_bytes() == before
    r2 = run(["migrate-backlog"], env, repo)
    assert r2.returncode != 0


def test_front_matter_and_a_fenced_hr_are_never_mistaken_for_the_header_rule(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    text = "---\ntitle: backlog\n---\n# B\n\n```\n---\n```\n\n---\n"
    _backlog(repo, text)
    _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)
    out_text = (repo / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
    assert out_text.index("title: backlog") < out_text.index("# B")
    assert out_text.index("# B") < out_text.index("<!-- AUTO-GENERATED:BACKLOG:START -->")
    # the fenced --- must not have been chosen as the insertion point either
    fence_idx = out_text.index("```\n---\n```")
    assert fence_idx < out_text.index("<!-- AUTO-GENERATED:BACKLOG:START -->")


def test_class_7_reads_only_the_trailing_id_not_one_embedded_in_a_title(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, "---\n")
    _ok(["add", "--kind", "backlog", "--title", "follow-up of W-deadbeef"], env, repo)
    _ok(["render"], env, repo)
    out1 = _ok(["sync", "--check"], env, repo)
    assert "DRIFT 7" not in out1
    out2 = _ok(["sync", "--check"], env, repo)
    assert "DRIFT 7" not in out2  # never a false-positive flap from the title's own fake id


def test_a_missing_block_with_open_items_is_class_7_drift(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _backlog(repo, "---\n")
    _ok(["add", "--kind", "backlog", "--title", "no block rendered yet"], env, repo)
    out = _ok(["sync", "--check"], env, repo)
    assert "DRIFT 7" in out


def test_class_7_is_silent_in_a_repo_with_no_backlog_file_at_all(tmp_path):
    """T09 review A-O5: distinct from the missing-BLOCK case above (a backlog file exists there,
    just with no rendered block yet) — here there is no docs/STRATEGIC_BACKLOG.md at all. An open
    backlog item with nothing to render into must never be flagged; `_backlog_needs_render`
    returns False before it ever reads the file."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _ok(["add", "--kind", "backlog", "--title", "an open item, no backlog file exists"], env, repo)
    assert not (repo / "docs" / "STRATEGIC_BACKLOG.md").exists()
    out = _ok(["sync", "--check"], env, repo)
    assert "DRIFT 7" not in out


# ── Decision T: an INDEPENDENTLY-written V2 reader ──────────────────────────────────────────────

_STATUS_WORDS = ("RESOLVED", "CLOSED", "DONE", "LANDED", "MOOT", "DRILLED", "SHIPPED")
_LEGEND_COLUMNS = ("Tag", "Agent", "Beat")


def _iv2_find_tag(s: str) -> tuple[str, tuple[int, int]] | None:
    """Own bracket scan (a manual index-walk, not `re.finditer`+shared regex) for the first bracket
    whose inner text is a plausible tag: starts with a lowercase letter or digit, is 1-32 chars of
    [a-z0-9-] before an optional `/`, `+` or unicode arrow compound tail, and is not a bare date or
    a checkbox mark."""
    pos = 0
    while True:
        open_at = s.find("[", pos)
        if open_at < 0:
            return None
        close_at = s.find("]", open_at)
        if close_at < 0:
            return None
        inner = s[open_at + 1 : close_at]
        pos = close_at + 1
        if inner in ("x", "X", " ", ""):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", inner):
            continue
        # A-O21: a cross-tag's separator may carry surrounding spaces ("infra + fleet")
        head = inner.split("/")[0].split("+")[0].split("→")[0].strip()
        if re.fullmatch(r"[a-z][a-z0-9-]{0,31}", head):
            return head.lower(), (open_at, close_at + 1)


_STAYS_OPEN_PHRASES = ("stays open", "still open", "remains open")


def _iv2_resolved(title_line: str, checkbox: str, strike_lead: bool, tag_span) -> bool:
    if checkbox.lower() == "x":
        return True
    if strike_lead:
        return True
    lowered = title_line.lower()
    if any(phrase in lowered for phrase in _STAYS_OPEN_PHRASES):
        return False
    # A-S3/A-O17: the checkmark joins the SAME word-boundary-respecting, status-position scan as
    # the uppercase words, rather than an unconditional "appears anywhere" test.
    markers: list[tuple[int, int, str]] = []
    for m in re.finditer("✅", title_line):
        markers.append((m.start(), m.end(), "✅"))
    for word in _STATUS_WORDS:
        start = 0
        while True:
            hit = title_line.find(word, start)
            if hit < 0:
                break
            start = hit + len(word)
            before_ch = title_line[hit - 1] if hit > 0 else " "
            after_ch = title_line[start] if start < len(title_line) else " "
            if before_ch.isalnum() or after_ch.isalnum():
                continue  # A-O17: a real word boundary on both sides, not a substring hit
            markers.append((hit, start, word))
    for hit, end, _word in sorted(markers):
        # A-O19: a status word directly preceded by PARTIALLY/PARTLY never resolves the row
        if re.search(r"\b(?:PARTIALLY|PARTLY)[ \t]*$", title_line[:hit], re.I):
            continue
        tail = title_line[end:]
        if re.match(r"^[\s:,\-—]{0,4}(\d{4}-\d{2}-\d{2}|in D-\d+)", tail):
            return True
        if tag_span is not None and hit >= tag_span[1]:
            gap = title_line[tag_span[1] : hit]
            if re.fullmatch(r"[\s*_~]*", gap):
                return True
        head = title_line[:hit]
        if re.search(r"—\s*$", head):
            return True
    return False


def _iv2_bracket_led(content: str) -> bool:
    probe = content.strip()
    for _ in range(3):
        if probe[:2] in ("~~", "**"):
            probe = probe[2:]
        elif probe[:1] == "`":
            probe = probe[1:]
        else:
            break
    return probe[:1] == "["


def _independent_scan(text: str) -> list[dict]:
    """A SECOND, independently-written reader of Decision R (row-start) and Decision M (resolved) —
    its own index-based bracket search, its own fence tracking, its own bullet/table detection —
    sharing no helper, regex object, or algorithm code with `work.py` or `docs_updater.py` (spec §
    Validation V2 / Decision T). Returns one dict per ROW: ``title`` (first line), ``body`` (full
    accumulated text), ``resolved``, ``owner``."""
    lines = text.split("\n")
    total = len(lines)
    out: list[dict] = []
    cur: dict | None = None
    buf: list[str] = []

    def close() -> None:
        nonlocal cur, buf
        if cur is not None:
            cur["body"] = "\n".join(buf).strip("\n")
            out.append(cur)
        cur, buf = None, []

    def open_row(owner: str, title_line: str, resolved: bool, shape: str) -> None:
        nonlocal cur, buf
        close()
        cur = {"title": title_line, "owner": owner, "resolved": resolved, "shape": shape}
        buf = [title_line]

    def absorb(raw_line: str) -> None:
        if cur is not None:
            buf.append(raw_line)

    fence_ch = ""
    fence_n = 0
    table_header: list[str] | None = None
    table_legend = False

    idx = 0
    while idx < total:
        raw = lines[idx]
        stripped = raw.strip()

        if fence_n:
            if re.match(r"^[" + re.escape(fence_ch) + r"]{" + str(fence_n) + r",}$", stripped):
                fence_n = 0
            absorb(raw)
            idx += 1
            continue
        fence_probe = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence_probe:
            fence_ch = fence_probe.group(1)[0]
            fence_n = len(fence_probe.group(1))
            absorb(raw)
            idx += 1
            continue

        if stripped[:1] == "|":
            sep_next = idx + 1 < total and re.match(
                r"^\|?[\s:|-]*-[\s:|-]*\|?$", lines[idx + 1].strip()
            )
            if sep_next:
                table_header = [c.strip() for c in stripped.strip("|").split("|")]
                table_legend = tuple(table_header) == _LEGEND_COLUMNS
                absorb(raw)
                idx += 1
                continue
            if table_header is not None and re.match(r"^\|?[\s:|-]*-[\s:|-]*\|?$", stripped):
                absorb(raw)
                idx += 1
                continue
            if table_header is not None and not table_legend:
                lowered = [c.lower() for c in table_header]
                tag_col = next(
                    (k for k, name in enumerate(lowered) if name in ("tag", "owner")), None
                )
                if tag_col is not None:
                    cells = [c.strip() for c in stripped.strip("|").split("|")]
                    if cells != table_header:
                        cell = cells[tag_col] if tag_col < len(cells) else ""
                        cell_stripped = cell.strip("`").strip()
                        found = _iv2_find_tag(cell_stripped)
                        if found:
                            owner = found[0]
                        elif re.fullmatch(r"[a-z0-9-]{1,32}", cell_stripped):
                            owner = cell_stripped
                        else:
                            owner = ""
                        # A-O18: the same resolved rule as any other row — the Item column (or
                        # cell 1, absent an "item" header) as strike-content, so a struck item
                        # (`~~Old item~~`) resolves.
                        item_col = next((k for k, name in enumerate(lowered) if name == "item"), 1)
                        item_cell = cells[item_col] if item_col < len(cells) else ""
                        struck_item = item_cell.lstrip().startswith("~~")
                        open_row(owner, raw, _iv2_resolved(raw, "", struck_item, None), "table")
                        idx += 1
                        continue
            absorb(raw)
            idx += 1
            continue
        table_header = None

        if raw.startswith("### "):
            content = raw[4:]
            found = _iv2_find_tag(content)
            span = found[1] if found else None
            resolved = _iv2_resolved(content, "", content.lstrip().startswith("~~"), span)
            if found or resolved:
                open_row(found[0] if found else "", raw, resolved, "heading3")
                idx += 1
                continue
            absorb(raw)
            idx += 1
            continue

        if raw.startswith("## "):
            content = raw[3:]
            found = _iv2_find_tag(content)
            span = found[1] if found else None
            resolved = _iv2_resolved(content, "", content.lstrip().startswith("~~"), span)
            open_row(found[0] if found else "", raw, resolved, "heading2")
            idx += 1
            continue

        if raw[:2] in ("- ", "* "):
            checkbox_match = re.match(r"^[-*] \[([ xX])\] (.*)$", raw)
            if checkbox_match:
                checkbox, content = checkbox_match.group(1), checkbox_match.group(2)
            else:
                checkbox, content = "", raw[2:]
            struck = content.lstrip().startswith("~~")
            if checkbox or struck or _iv2_bracket_led(content):
                found = _iv2_find_tag(content)
                span = found[1] if found else None
                resolved = _iv2_resolved(content, checkbox, struck, span)
                open_row(found[0] if found else "", content, resolved, "bullet")
                idx += 1
                continue

        absorb(raw)
        idx += 1

    close()
    return out


def test_independent_scan_agrees_with_the_scanner_on_the_fixture(tmp_path):
    """A sanity check on the small fixture BEFORE trusting the independent reader on the real hub
    file: it must find the same row count and the same open/done split as the scanner it is meant
    to cross-check (a fixture small enough to hand-verify)."""
    rows = _independent_scan(FIXTURE)
    assert len(rows) == 11, [r["title"] for r in rows]
    open_n = sum(1 for r in rows if not r["resolved"])
    done_n = sum(1 for r in rows if r["resolved"])
    assert open_n == 7
    assert done_n == 4


def test_migrate_backlog_then_render_matches_an_independent_reader_on_the_hub_backlog(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    hub_text = HUB_BACKLOG.read_text(encoding="utf-8")
    _backlog(repo, hub_text)
    out = _ok(["migrate-backlog"], env, repo)
    _ok(["render"], env, repo)

    items = _backlog_items(repo)
    open_n = sum(1 for it in items if it["status"] == "open")
    done_n = sum(1 for it in items if it["status"] == "done")

    ref_rows = _independent_scan(hub_text)
    exp_open = sum(1 for r in ref_rows if not r["resolved"])
    exp_done = sum(1 for r in ref_rows if r["resolved"])

    print(f"\nT03 review pass-1 hub counts: rows={len(ref_rows)} open={exp_open} done={exp_done}")
    print(f"migrate-backlog: {out.splitlines()[0]}")

    assert len(items) == len(ref_rows), (len(items), len(ref_rows))
    assert open_n == exp_open, (open_n, exp_open)
    assert done_n == exp_done, (done_n, exp_done)

    # every source row's title text is the FIRST LINE of exactly as many items as it occurs in the
    # source (Decision R.7 — two genuinely duplicated rows are two items, so a title's count must
    # MATCH, not just be nonzero) — an exact correspondence, never a substring search (a title can
    # legitimately be quoted or referenced inside another, unrelated row's body prose, which a bare
    # "in" check would misread as a spurious extra match).
    item_first_lines: dict[str, list[str]] = {}
    for it in items:
        first = str(it["next"]).split("\n", 1)[0]
        item_first_lines.setdefault(first, []).append(str(it["next"]))
    ref_title_counts: dict[str, int] = {}
    for ref in ref_rows:
        title = ref["title"].strip()
        if title:
            ref_title_counts[title] = ref_title_counts.get(title, 0) + 1
    for title, expected_count in ref_title_counts.items():
        owning = item_first_lines.get(title, [])
        assert len(owning) == expected_count, (title[:80], expected_count, len(owning))

    # A-O22: the OWNER must also match — reverting `_find_first_tag` to position-0-only silently
    # changes which rows get which owner without changing any count the checks above would catch.
    item_owners_by_title: dict[str, list[str]] = {}
    for it in items:
        first = str(it["next"]).split("\n", 1)[0]
        item_owners_by_title.setdefault(first, []).append(str(it.get("owner") or ""))
    ref_owners_by_title: dict[str, list[str]] = {}
    for ref in ref_rows:
        title = ref["title"].strip()
        if title:
            ref_owners_by_title.setdefault(title, []).append(ref["owner"])
    for title, ref_owners in ref_owners_by_title.items():
        got = item_owners_by_title.get(title, [])
        assert sorted(got) == sorted(ref_owners), (title[:80], ref_owners, got)

    # every 20th row's body text appears in ONE of the items sharing that title
    for i in range(0, len(ref_rows), 20):
        ref = ref_rows[i]
        title = ref["title"].strip()
        if not title:
            continue
        body = ref["body"].strip()
        owning = item_first_lines[title]
        needle = body[: min(len(body), 400)]
        assert any(needle in text for text in owning), title[:80]

    # B-S3-residual: the every-20th sample never happens to land on a bullet row with genuine
    # continuation lines at hub scale, so every SUCH bullet is checked explicitly here — reverting
    # bullet-body accumulation to first-line-only must turn this red.
    bullet_with_continuation = [r for r in ref_rows if r["shape"] == "bullet" and "\n" in r["body"]]
    assert bullet_with_continuation, "expected at least one hub bullet with continuation lines"
    for ref in bullet_with_continuation:
        title = ref["title"].strip()
        owning = item_first_lines[title]
        continuation = ref["body"].split("\n", 1)[1]
        assert any(continuation in text for text in owning), title[:80]

    # a second migrate-backlog run against the SAME file creates nothing further
    before = len(items)
    _ok(["migrate-backlog"], env, repo)
    assert len(_backlog_items(repo)) == before
