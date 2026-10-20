"""The subagent definitions are GENERATED from the repo, not hand-authored on the box.

Before this, `~/.claude/agents/` held four definitions (214 lines) that existed ONLY on this
machine: no repo source, no generator, not in git, invisible to `check_command_corpus.py` and to
every sync. Three consequences, all real:

- a defect in a subagent's brief could not be reviewed, because there was nothing to diff;
- the corpus check audited 31 commands and 31 skills while the agents those commands DISPATCH were
  outside its jurisdiction entirely — the same blind spot that once left the orchestrator wrappers
  unaudited (`docs/reference/command-corpus-check.md` § The orchestrator corpus);
- the obligations every command carries (the feedback duty) could not reach them.

The sources are now `commands/_agents/*.md` and the renderer owns the destination, exactly as it
already owns `~/.claude/commands` and `~/.claude/skills`.
"""

from __future__ import annotations

import importlib.util
import re
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("asm", REPO / "commands" / "assemble_commands.py")
assert _spec and _spec.loader
asm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asm)

SRC = REPO / "commands" / "_agents"
MARKER = "## ⚠️ Machinery findings"


def _render() -> Path:
    tmp = Path(tempfile.mkdtemp())
    asm.render(tmp, tmp / "_skills", agents_dest=tmp / "_agents")
    return tmp / "_agents"


def test_every_source_agent_is_rendered():
    out = _render()
    srcs = {p.name for p in SRC.glob("*.md")}
    assert srcs, "no agent sources — the harness is broken, not the assertion"
    assert {p.name for p in out.glob("*.md")} == srcs


def test_a_blank_line_in_the_frontmatter_fails_the_render_loudly():
    """The defect that hid `fabrik-reviewer` from the agent roster: a second paragraph inside the
    `description:` scalar. A blank line at column 0 ends a plain YAML scalar, so the loader dropped
    the definition — while every check stayed green, because the FILE renders perfectly. The only
    symptom was a Task dispatch answering "agent type not found", mid-review, one seat short."""
    good = "---\nname: x\ndescription: one line\ntools: Read\n---\n\nbody\n"
    assert asm._agent_frontmatter_defect(good) is None
    bad = "---\nname: x\ndescription: one line\n\n**A second paragraph.**\n\ntools: Read\n---\n\nbody\n"
    assert "blank line" in (asm._agent_frontmatter_defect(bad) or "")
    assert "no `name:` key" in (
        asm._agent_frontmatter_defect("---\ndescription: d\n---\nb\n") or ""
    )
    assert asm._agent_frontmatter_defect("no frontmatter at all\n")


def test_every_agent_source_would_actually_register():
    """The live sources, not a fixture: each must survive the loader, or the seat does not exist."""
    broken = {
        p.name: asm._agent_frontmatter_defect(p.read_text(encoding="utf-8"))
        for p in SRC.glob("*.md")
    }
    assert not {k: v for k, v in broken.items() if v}, broken


def test_every_rendered_agent_carries_the_machinery_duty():
    out = _render()
    missing = [p.name for p in out.glob("*.md") if MARKER not in p.read_text(encoding="utf-8")]
    assert not missing, f"agents shipping without the machinery duty: {missing}"


def test_the_duty_is_appended_once():
    out = _render()
    for p in out.glob("*.md"):
        assert p.read_text(encoding="utf-8").count(MARKER) == 1, p.name


def test_the_frontmatter_survives_rendering():
    """Claude Code parses `name:`/`description:`/tool fields out of the frontmatter — a renderer
    that disturbed the block would silently unregister the agent."""
    out = _render()
    for p in out.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{p.name}: frontmatter must lead the file"
        head = text.split("\n---", 1)[0]
        assert "name:" in head and "description:" in head, f"{p.name}: {head[:80]}"


def test_the_rendered_name_matches_the_filename():
    """A `name:` that disagrees with its filename registers an agent nobody can dispatch by path."""
    out = _render()
    for p in out.glob("*.md"):
        head = p.read_text(encoding="utf-8").split("\n---", 1)[0]
        declared = next(
            ln.split(":", 1)[1].strip() for ln in head.splitlines() if ln.startswith("name:")
        )
        assert declared == p.stem, f"{p.name} declares name: {declared}"


def test_a_generated_orphan_is_pruned_but_a_hand_authored_file_is_not():
    """Same contract the command renderer already keeps: prune what WE generated, never touch a file
    a human put there. Deleting an operator's local agent would be data loss."""
    out = _render()
    (out / "gone.md").write_text(asm.BANNER + "---\nname: gone\n---\n", encoding="utf-8")
    (out / "mine.md").write_text("---\nname: mine\n---\nhand-authored\n", encoding="utf-8")
    asm.render(out.parent, out.parent / "_skills", agents_dest=out)
    assert not (out / "gone.md").exists(), "a generated orphan must be pruned"
    assert (out / "mine.md").exists(), "a hand-authored file must survive"


def test_check_detects_drift_in_a_rendered_agent():
    """`--check` is what makes the sources CANONICAL rather than merely first."""
    out = _render()
    target = out / "fabrik-reviewer.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nhand-edited\n", encoding="utf-8")
    drift = asm.agent_drift(out)
    assert any("fabrik-reviewer" in d for d in drift), drift


@pytest.mark.live_box
def test_the_live_box_matches_the_repo_sources():
    """The point of the whole change: what the box actually dispatches is what the repo says."""
    drift = asm.agent_drift(asm.AGENTS)
    assert drift == [], f"~/.claude/agents drifted from commands/_agents: {drift}"


def test_every_agent_definition_carries_the_git_verb_prohibition():
    """Spec D8 (pass 3): every native seat definition carries the shared git-verb sentence — a
    reviewer seat's `git stash --keep-index` swept three sessions' uncommitted work mid-pass
    (2026-09-11). Asserted on the SOURCES, per file, by the key phrase."""
    phrase = "no git command that mutates state"
    srcs = sorted(SRC.glob("*.md"))
    assert len(srcs) == 4, [p.name for p in srcs]
    missing = [p.name for p in srcs if phrase not in p.read_text(encoding="utf-8").lower()]
    assert not missing, missing


def test_the_stash_recovery_recipe_is_byte_identical_in_both_contracts():
    """The recipe sentence (pass 3, spec D8) lives INSIDE the § Shared repo bullet of both
    contracts; the bullets differ by design, the recipe substring — from the start anchor to the
    end anchor inclusive — must not."""
    start, end = "git stash show --name-only 'stash@{0}'", "never a pop"

    def recipe(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        i = text.find(start)
        assert i >= 0, f"{path.name}: start anchor absent"
        j = text.find(end, i)
        assert j >= 0, f"{path.name}: end anchor absent after the start anchor"
        return text[i : j + len(end)]

    hub = recipe(REPO / "CLAUDE.md")
    tpl = recipe(REPO / "templates" / "governance" / "CLAUDE.md")
    assert hub == tpl
    assert "git show 'stash@{0}':<path>" in hub


def test_the_mail_triage_agent_sentences_are_present_once():
    """T2.12: the reviewer reads a materialised tree or a commit with `git -C <repo> show`;
    T2.19: the researcher names the two exa web_fetch drops (tables, late sections)."""
    reviewer = (SRC / "fabrik-reviewer.md").read_text(encoding="utf-8")
    researcher = (SRC / "fabrik-researcher.md").read_text(encoding="utf-8")
    assert reviewer.count("with `git -C <repo>` when the repo is not your cwd") == 1
    assert researcher.count("silently DROPS TABLES") == 1


def test_the_researcher_follows_redirects_and_pages_before_an_absence():
    """W-eb9db7c0: WebFetch returns a cross-host redirect unfollowed and reads a long page in
    windows, so the researcher re-fetches the redirect target and pages on with `offset` before
    an ABSENCE verdict."""
    researcher = " ".join((SRC / "fabrik-researcher.md").read_text(encoding="utf-8").split())
    assert "six measured failure shapes" in researcher
    assert "`REDIRECT DETECTED` reply naming the server's `Location` URL" in researcher
    assert "fetch that URL and cite both the original and the final one" in researcher
    assert "line that the TOOL appends after the answer" in researcher
    assert "Before any ABSENCE verdict on that page, call again with that `offset`" in researcher
    assert "a `NEEDS-RAW-FETCH` naming the next offset, never an absence" in researcher
    assert "Paging is necessary, not sufficient" in researcher
    assert "try `mcp__exa__web_fetch_exa` once; only if both fail" in researcher
    assert "judging the claim on the final page like any other" in researcher
    assert "VERIFIED|INFERENCE|STALE|WRONG|DEAD|NEEDS-RAW-FETCH|UNVERIFIABLE" in researcher


def test_the_researcher_returns_a_bounded_inference_verdict():
    """W-0c33e10f (W-8bc61173 residue; Opus + Fable critiques): the INFERENCE that shapes 2 and 4 mark is a return
    verdict, bounded so it is no escape from a raw fetch, an ABSENCE bar or a NEEDS-RAW-FETCH handoff; a figure
    read only from exa's crawl cache grounds neither VERIFIED nor STALE; NEEDS-RAW-FETCH admits shape 4's
    only-source dead page. Each sentence is pinned whole inside its section (Method, Return format)."""
    raw = (SRC / "fabrik-researcher.md").read_text(encoding="utf-8")
    method = " ".join(raw[raw.index("## Method") : raw.index("## Return format")].split())
    returns = " ".join(raw[raw.index("## Return format") :].split())
    assert (
        "`<claim> → VERIFIED|INFERENCE|STALE|WRONG|DEAD|NEEDS-RAW-FETCH|UNVERIFIABLE ·" in returns
    )
    inference = (
        "- `INFERENCE` — no line states the claim but what you read implies it (a mapping, a derived figure): only "
        "after a raw fetch or a second arm still quotes no line (name the arms tried), never for an ABSENCE (shape "
        "4's bar), and never where a curl of a named URL would settle it — that is a `NEEDS-RAW-FETCH`. Give the "
        "reasoning and the URL it rests on."
    )
    for span in (
        inference,
        "- `WRONG` / `DEAD` — the citation doesn't support the claim / the URL 404s on a live fetch too (shape 4: "
        "a `WebFetch` 404 alone is not `DEAD`; a claim's only source dead live is a `NEEDS-RAW-FETCH`).",
        "- `NEEDS-RAW-FETCH` — the source exists (or existed) but this toolset",
        "· a redirect chain or page tail shape 6 could not finish · an only-source page dead on the live fetch, "
        "shape 4 · a changing figure no live arm reached, step 5)",
    ):
        assert method.count(span) == 1, span
    # the verdict list is ordered: INFERENCE sits between VERIFIED and STALE (review pass 1, M2)
    assert method.index("- `VERIFIED` —") < method.index(inference) < method.index("- `STALE` —")
    flat = " ".join(raw.split())
    assert "version-specific figure on a docs page read only from exa" not in flat  # the narrow rule is gone
    # W-c01b59db: exa's fetch sends no live-crawl setting, so any page may be its cache; WebFetch only confirms.
    # Each sentence is held inside its own step or shape, so a sentence moved elsewhere goes red too.
    step5 = " ".join(raw[raw.index("5. **Freshness binds:**") : raw.index("## Return format")].split())
    for span in (
        "A claim about a CURRENT value — one that can change after the page was written, such as a price, a rate "
        "limit or usage limit, a quota, a default, a current or supported version, or a status (available, "
        "deprecated) — read only from a cached arm (exa, whose fetch sends no live-crawl setting, so any page it "
        "returns may be its crawl cache — measured 2026-10-20; firecrawl without `maxAge: 0`; a search result or "
        "its answer) is not live: neither `VERIFIED`, `STALE` nor `WRONG` rests on it without a live read.",
        'Firecrawl `maxAge: 0` is that read (with `parsers: ["pdf"]` for a PDF).',
        # review pass 2: agreement makes the VALUE live; the verdict still compares it with the claim
        "A `WebFetch` answer, asked for the value without being told it, only confirms: when it states the value "
        "a raw arm quoted, that value is live — `VERIFIED` when the claim states it, `STALE` when the claim "
        "states another; any other value it states (a different one, or one no raw arm quoted) is settled by "
        "firecrawl `maxAge: 0`, else the verdict is `NEEDS-RAW-FETCH` — as it is when no live arm reaches a page "
        "that is not a live 404 (shape 4 decides that).",
        "A quote's wording stays shape 1's and a PDF's text shape 3's — only the claim about the current value "
        "needs the live read — and a figure inside a document fixed once published (a published paper, a filing, "
        "a dated changelog entry, a versioned release note) is not a changing one, though which entry or release "
        'is the newest is a current value; a page\'s "last updated" stamp does not make it fixed.',
    ):
        assert step5.count(span) == 1, span
    shape3 = " ".join(raw[raw.index("  3. ") : raw.index("  4. ⚠️")].split())
    assert shape3.count(
        "exa can serve an out-of-date copy of any page (Method step 5) — for a version-specific claim on a docs "
        "page, cross-check live (step 5), which decides which version is current."
    ) == 1
    assert "cross-check with `WebFetch`" not in flat and "quote the arm carrying the newer version notes" not in flat
    # shape 2's markup quote is a NEEDS-RAW-FETCH, never INFERENCE (review pass 1: the bound and shape 2 clashed)
    assert (
        "Return `NEEDS-RAW-FETCH` (below) so the caller curls it — a curl settles a verbatim quote, so it is never "
        "`INFERENCE`." in flat
    )
    assert "Mark the mapping INFERENCE" not in flat


def test_the_researcher_names_the_quote_arm_and_the_positive_synthesis_bar():
    """W-8bc61173 (mail 01M4VHFP7S, 3 of 4 seats in one pass): exa's `maxCharacters` lever and its cut reply;
    exa for a short page and firecrawl's directQuote call FIRST for a long one, prompted by a locator, compared
    character by character, re-asked on a wrong-place excerpt; and a summariser's "documents X" claim or a WebFetch
    404 held to shape 4's bar. Each directive is asserted whole and inside its shape, and there are still six
    shapes (scoped review passes 1 and 2: partial spans survived meaning-reversing mutants)."""
    raw = (SRC / "fabrik-researcher.md").read_text(encoding="utf-8")
    researcher = " ".join(raw.split())
    block = raw[raw.index("Fetch-path routing") : raw.index("- **Library/API docs:**")]
    assert len(re.findall(r"(?m)^  \d\. ", block)) == 6
    flat = " ".join(block.split())
    s1, s2 = (
        flat.index("1. A `WebFetch` reply"),
        flat.index("2. **The raw arm silently drops angle-bracket"),
    )
    s4, s5 = (
        flat.index("4. ⚠️ **A summariser answering ABSENCE"),
        flat.index("5. **The raw arm silently DROPS"),
    )
    for span in (
        "on `mcp__exa__web_fetch_exa` set `maxCharacters` to 25000 or less",
        "A reply that stops at exactly the cap was cut, not finished; a source file longer than the cap goes to "
        "shape 1's long-page call or a `NEEDS-RAW-FETCH`, never to a bigger fetch",
        "- `WRONG` / `DEAD` — the citation doesn't support the claim / the URL 404s on a live fetch too "
        "(shape 4: a `WebFetch` 404 alone is not `DEAD`;",
    ):
        assert span in researcher, span
    # shape 1 asks again ONCE: no second re-ask clause survives anywhere in the shape (review pass 1, M6)
    shape1 = " ".join(block[block.index("  1. ") : block.index("  2. ")].split())
    assert shape1.count("ask again") == 1 and "as many times" not in shape1
    for lo, hi, span in (
        (s1, s2, "use `mcp__exa__web_fetch_exa` on a SHORT page"),
        (
            s1,
            s2,
            "On a LONG page (a source file, a long reference page — anything longer than exa's cap) go to firecrawl "
            'FIRST instead — `mcp__firecrawl__firecrawl_scrape` with `formats: ["query"]`, `queryOptions: {"mode": '
            '"directQuote", "prompt": "<a locator: the symbol or the heading the span sits under>"}` and `maxAge: 0`',
        ),
        (
            s1,
            s2,
            "compare the returned excerpt character by character with the claimed quote, and name the fetch path "
            "in the verdict.",
        ),
        (s1, s2, "Never put the claimed quote's wording in the prompt"),
        (
            s1,
            s2,
            "An excerpt from the wrong place proves nothing either way: narrow the locator and ask again — once: a "
            "second wrong-place excerpt, or an empty or not-found reply, counts as a miss; if firecrawl still misses, refuses or errors, fall back to exa, which reads only the first 25000 "
            "characters (no offset, shape 4), so a span past them is a `NEEDS-RAW-FETCH` — never `WRONG` on one "
            "excerpt.",
        ),
        (s1, s2, "An empty or not-found reply is an ABSENCE answer under shape 4."),
        (
            s4,
            s5,
            "The same bar binds a summariser's claim that a page DOCUMENTS something, when the verdict rests on "
            "that claim rather than on a line you quoted: quote the line from a raw fetch or a second arm, or return "
            "`INFERENCE` (Method step 4: name the arms tried) when no line states it but what you read implies "
            "it, else `WRONG` — and `NEEDS-RAW-FETCH` instead of either when no arm could read the page faithfully "
            "(a markup, table, tail or non-HTML bound — shapes 2, 3, 5, 6) and a curl of a named URL would settle "
            "it",
        ),
        (s4, s5, "JSON/XML keeps shape 3's routing."),
        (
            s4,
            s5,
            "a `WebFetch` 404 is not `DEAD` until `mcp__firecrawl__firecrawl_scrape` with `maxAge: 0` (a live "
            "fetch) also answers 404 — then it is `DEAD` (unless it was the claim's only source — below), even if "
            "exa still serves a copy (cite that copy as exa's crawl cache); a page firecrawl serves live is not dead.",
        ),
        (
            s4,
            s5,
            "so a claim whose only source is a since-deleted page — a live 404 included, with no other source after "
            "searching both engines for one — is a `NEEDS-RAW-FETCH`, not an absence: its fact field says the URL is `DEAD` "
            "on the live fetch, cites any exa copy as crawl cache, and names `https://web.archive.org/web/2/<url>`, "
            "which redirects to the newest capture (measured 2026-10-19).",
        ),
        (
            s4,
            s5,
            "A firecrawl error that is not a 404 (credit, auth, a timeout) decides nothing: the verdict is then "
            "`NEEDS-RAW-FETCH`, and a copy exa serves meanwhile is its crawl cache, never `VERIFIED`",
        ),
    ):
        at = flat.find(span)
        assert at != -1, span
        assert lo < at < hi, ("misplaced", span)
