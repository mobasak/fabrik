"""D-192 — the assembler grades D-191: a rendered command that fans out must carry the dispatch step.

The rule multiplied fleet spend with zero graders (the D-191 review's Opus seat: `grep -rn
dispatch_headroom scripts/enforcement/ .claude/hooks/` printed nothing; 0 of 97 recorded rounds
carried `--seats`). `dispatch_step_gaps` is the cheapest real one — measured on the 36 rendered
commands before it shipped: 27 fan out and carry the step, 3 fanned out without it, 6 are serial by
design and match neither, 0 false positives. And the judgement-kind floors (grounding, adjudication)
name no Haiku seat: a judgement unit has no grep-able angle.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ac", REPO / "commands" / "assemble_commands.py")
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)

STEP = (
    "**Dispatch step (D-191):** run `dispatch_headroom.py --units <N>` and dispatch what it prints."
)


def test_a_command_that_fans_out_without_the_dispatch_step_is_a_gap():
    rendered = {
        "fans-out-covered": "dispatch one seat per screen, all in a single message. " + STEP,
        "fans-out-bare": "dispatch **one `fabrik-reviewer` seat per claim, all in a single message**.",
        "fans-out-verb": "Finders are dispatched together in ONE message so they run in parallel.",
        "serial-by-design": "Walk the checklist yourself; no subagent is dispatched here.",
        # "seats per" in prose about cost is not a fan-out (round-4: the branch was untethered)
        "prose-only": "Fewer seats per round drops recall; the seat per group ratio is a budget matter.",
        "step-no-fanout": "THE DISPATCH STEP (D-191, binding on every fan-out): …",
        # the named-unit branch alone: no "seat", no "dispatch" — one reader per file
        "fans-out-named": "Run one `fabrik-reviewer` per file, all in ONE message; merge the union.",
        # a step that survives only inside a POOL-OFF comment does not cover the live text
        "fans-out-masked": "one seat per claim, all in a single message. <!-- POOL OFF: "
        + STEP
        + " -->",
    }
    assert ac.dispatch_step_gaps(rendered) == [
        "fans-out-bare",
        "fans-out-masked",
        "fans-out-named",
        "fans-out-verb",
    ]


def test_the_live_corpus_has_no_gap_and_the_detector_fires_on_real_fan_outs(tmp_path):
    """Executed on the rendered corpus, not asserted from the source list: every command that fans
    out carries the step, and the detector is not wallpaper — it fires on the real fan-outs."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    rendered = {f.stem: f.read_text() for f in tmp_path.glob("*.md")}
    assert len(rendered) >= 30
    assert ac.dispatch_step_gaps(rendered) == []
    fan = [n for n, t in rendered.items() if ac._FANOUT_RE.search(t)]
    assert len(fan) >= 25, fan  # 30 of 36 when this shipped
    assert {"fabrik-review", "design-review", "fabrik-rivals", "fabrik-upstream"} <= set(fan)
    # round-8 Opus finding: the ten short banners kept the pre-F189 wording and dropped
    # `--mechanical` — the only flag list in four commands. One wording, every flag, box-wide.
    graded = 0
    for name, text in rendered.items():
        live = ac._HTML_COMMENT_RE.sub("", text)
        assert "stamped first with" not in live, name
        for m in re.finditer(r"--units <N>[^`]*\[--risky <R>\][^`]*`", live):
            graded += 1
            assert "[--mechanical <M>]" in m.group(0), (name, m.group(0))
    assert graded >= 25, graded  # a reworded banner must not empty the grader (round 9)
    # the fragment's partial-close clause survives a render (round 13: appendix-only prose
    # with no grader); fabrik-review includes the fragment
    live_review = ac._HTML_COMMENT_RE.sub("", rendered["fabrik-review"])
    assert "keeps the remainder on the ORIGINAL stamp's clock" in live_review


def test_judgement_floors_name_no_haiku_seat_and_review_floors_name_a_class_wide_one():
    grounding = ac._floor("grounding", "`fabrik-researcher`")
    review = ac._floor("review", "`fabrik-reviewer`")
    assert "no mechanical seat" in grounding and "--mechanical 0" in grounding
    assert "haiku" not in grounding.lower()
    # both judgement kinds — dropping "adjudication" from the set reopened F27 unnoticed (round 4)
    adjudication = ac._floor("adjudication", "`fabrik-reviewer`")
    assert "an adjudication unit" in adjudication and "haiku" not in adjudication.lower()
    # D-208: the units-sized mix stays for the sweep/audit/docs-review/review kinds, rephrased
    # off the retired D-191 literal — one Haiku seat per grep-able CLASS, not per unit.
    assert "one Haiku mechanical seat per grep-able class the surface has" in review
    assert "sweeps ONE class across every unit" in review
    assert "units-sized mix for a review, docs-review, sweep or audit surface" in review


# The ticket fixes both floor sentences VERBATIM so a grader can assert them WHOLE. A clause-level
# check is not enough: two mutants of the partition floor — `(D-207)` -> `(D-999)` and the deletion
# of the Haiku-class-seat clause — survived every earlier assertion in this file (review round 1).
_PARTITION_SENTENCE = (
    "**plus the partition — the surface cut into DISJOINT slices by file: Opus on the risky "
    "slices, Sonnet `fabrik-reviewer` seats on the rest, at most ONE Haiku class seat when the "
    "brief names a non-scriptable inventory class; every file read once; sized by "
    "`dispatch_headroom.py --slices opus=N,sonnet=N,haiku=N` (D-207)"
)


def _units_sentence(native: str) -> str:
    """The D-208 sentence as it renders for a given `{native}` token — the `else`-branch commands
    use `fabrik-reviewer` or `fabrik-researcher`, so a single literal grades only half of them."""
    return (
        f"**plus one Sonnet {native} breadth seat per INDEPENDENT unit and one Haiku "
        "mechanical seat per grep-able class the surface has (trimmed, each Haiku seat sweeps ONE "
        "class across every unit) — the units-sized mix for a review, docs-review, sweep or audit "
        "surface (D-208)"
    )


_UNITS_SENTENCE = _units_sentence("`fabrik-reviewer`")


def test_the_two_partitioned_review_loops_get_the_slice_floor_and_nothing_else_does():
    """D-207 gives the partition ONLY to `/fabrik-review` and `/fabrik-repo-review`, through a
    third `_floor` kind. Graded on the PARAMS table, not on a source list: a fourth command
    silently switched to the `review loop` kind is exactly the drift this catches."""
    loop = ac._floor("review loop", "`fabrik-reviewer`")
    assert _PARTITION_SENTENCE in loop, loop  # WHOLE, including the D-row cite
    assert "one Haiku mechanical seat per grep-able class" not in loop
    # the D-208 sentence is fixed verbatim too — the same mutant class, the other branch
    assert _UNITS_SENTENCE in ac._floor("review", "`fabrik-reviewer`")
    slice_floors = sorted(
        name
        for name, frags in ac.PARAMS.items()
        if _PARTITION_SENTENCE in (frags.get("subagents-core", {}).get("FLOOR") or "")
    )
    assert slice_floors == ["fabrik-repo-review", "fabrik-review"], slice_floors


_DELTA_CLAUSE = (
    "a delta round at or under the fragment's budget dispatches ONE fresh seat plus the hygiene "
    "script (`--delta`, D5)"
)


def test_the_two_partition_floors_carry_the_delta_clause_and_the_judgement_floors_do_not():
    """D5 (review-family pass 3, D-229): round 1 keeps its partition; every later round is sized
    by the fix — the two partition FLOOR sentences say so, the judgement kinds (no partition,
    `--mechanical 0`) do not."""
    for kind in ("review loop", "section partition"):
        assert _DELTA_CLAUSE in ac._floor(kind, "`fabrik-reviewer`"), kind
    for kind in ("grounding", "adjudication"):
        assert _DELTA_CLAUSE not in ac._floor(kind, "`fabrik-reviewer`"), kind


_SECTION_PARTITION_SENTENCE = (
    "plus the partition — the artifact cut into DISJOINT slices by SECTION: Opus on the "
    "rule/grammar sections, Sonnet `fabrik-reviewer` seats on the rest, `fabrik-researcher` seats "
    "only for the external facts the artifact cites (counted inside `opus=`/`sonnet=` by their model "
    "token), NO Haiku seat (the hygiene script is the class sweep); sized by "
    "`dispatch_headroom.py --slices opus=N,sonnet=N` (D-207, D-218)"
)


def test_the_term_edit_review_family_gets_the_section_partition_floor_and_nothing_else_does():
    """D-212/D-218 (review-family adoption): `/fabrik-spec-review` and `/fabrik-plan-review` partition by
    SECTION, through a fourth `_floor` kind of their own. Reusing the file-partition kind would render
    "at most ONE Haiku class seat" and lose the judgement kinds' `--mechanical 0` clause — so the
    sentence is graded WHOLE and for the absence of both, on the PARAMS table (a third command
    silently switched to the kind is the drift this catches)."""
    floor = ac._floor("section partition", "`fabrik-reviewer`")
    assert _SECTION_PARTITION_SENTENCE in floor, floor
    assert "Haiku mechanical seat" not in floor and "Haiku class seat" not in floor, floor
    assert "--mechanical" not in floor, floor
    section_floors = sorted(
        name
        for name, frags in ac.PARAMS.items()
        if _SECTION_PARTITION_SENTENCE in (frags.get("subagents-core", {}).get("FLOOR") or "")
    )
    assert section_floors == ["fabrik-plan-review", "fabrik-spec-review"], section_floors
    # the file-partition kind is untouched by the new one
    assert _SECTION_PARTITION_SENTENCE not in ac._floor("review loop", "`fabrik-reviewer`")


def test_every_extract_after_text_round_trips_against_its_source():
    """`extract()` REWRITES `_sources/*.md` from the installed backup using each EXTRACT entry's
    after-text — a stored copy of prose the source owns. Two stale copies were found by hand on
    2026-09-10 (a retired exit wording; a dropped `python ` in a runnable line); this is the grader
    that hand check lacked: for every entry with an after-text, the source's text right after its
    `{{include:<fragment>}}` marker IS that string."""
    src_dir = REPO / "commands" / "_sources"
    examined, mismatched = 0, []
    for name, plan in ac.EXTRACT.items():
        source = (src_dir / f"{name}.md").read_text()
        for _block, fragment, after in plan:
            examined += 1
            marker = "{{include:" + fragment + "}}"
            assert marker in source, (name, fragment)
            # `extract()` replaces the WHOLE rendered section with marker + after-text, so the
            # round-trip holds only if NOTHING else sits between the marker and the next include
            # or heading — a prefix compare would let trailing source prose be silently deleted
            start = source.index(marker) + len(marker)
            tail = source[start:]
            end = min(
                (i for i in (tail.find("\n{{include:"), tail.find("\n#")) if i >= 0),
                default=len(tail),
            )
            kept = tail[:end].strip("\n")
            if kept != (after or "").strip("\n"):
                mismatched.append((name, fragment, kept[:60]))
    # every entry, none skipped — and an absolute floor, so an emptied EXTRACT cannot read green
    # pinned to the map's size on purpose: a map that lost 23 of its 29 after-texts read green under
    # a `>= 6` floor — changing EXTRACT means changing this number deliberately
    assert examined == sum(len(p) for p in ac.EXTRACT.values()) == 34, examined  # +5: pass 3, D1
    assert mismatched == [], mismatched


def test_both_floor_sentences_reach_their_rendered_commands_whole(tmp_path):
    """`_floor()` alone cannot see an interpolation or PARAMS change that mangles a sentence on its
    way into a command — grade the RENDERED text, comments stripped, and count the carriers. BOTH
    sentences: grading only the partition one left a D-208-cite mutant red at `_floor()` level and
    green here (delta round 2)."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    rendered = {f.stem: ac._HTML_COMMENT_RE.sub("", f.read_text()) for f in tmp_path.glob("*.md")}
    partition = sorted(n for n, text in rendered.items() if _PARTITION_SENTENCE in text)
    assert partition == ["fabrik-repo-review", "fabrik-review"], (partition, len(rendered))
    # The units sentence interpolates `{native}`, so it renders in TWO shapes — assert BOTH, by
    # command NAME, so dropping one from PARAMS is not absorbed by a count with slack, and the two
    # partitioned loops must appear in NEITHER (D-208 vs D-207).
    units = {
        native: sorted(n for n, text in rendered.items() if _units_sentence(native) in text)
        for native in ("`fabrik-reviewer`", "`fabrik-researcher`", "`design-review`")
    }
    assert units == {
        "`fabrik-reviewer`": ["fabrik-doc-converge", "fabrik-features"],
        # the third carrier (review-family pass 3, D1): /design-review keeps its mechanical seat
        "`design-review`": ["design-review"],
        # `/fabrik-spec-review` left this list for the SECTION-partition floor (D-212/D-218)
        "`fabrik-researcher`": [
            "fabrik-docs-review",
            "fabrik-flows-review",
            "fabrik-rules-review",
            "fabrik-ui-design-review",
            "fabrik-workflow-review",
        ],
    }, (units, len(rendered))
    assert not {"fabrik-review", "fabrik-repo-review"} & {n for v in units.values() for n in v}


def test_the_native_half_of_a_commands_extra_renders_in_the_live_paragraph(tmp_path):
    """Round-5 finding: `{{EXTRA}}` sits inside the <!-- POOL OFF --> comment, so /fabrik-spec's
    "an EMPTY grounding is a FAILED grounding" was invisible while the pool is OFF. `{{EXTRA_LIVE}}`
    carries the pool-independent sentences into the live paragraph; a command without one renders
    nothing there (no unfilled placeholder)."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    spec = (tmp_path / "fabrik-spec.md").read_text()
    live = ac._HTML_COMMENT_RE.sub("", spec)
    assert "EMPTY (or near-empty) grounder output is a FAILED grounding" in live
    assert all("{{EXTRA_LIVE}}" not in f.read_text() for f in tmp_path.glob("*.md"))


def test_a_judgement_floor_span_never_names_a_haiku_seat_in_the_rendered_text(tmp_path):
    """Round-7 finding: `_floor("grounding")` says "no mechanical seat … `--mechanical 0`" and the
    same command's `{{EXTRA_LIVE}}`, concatenated right after it, said "Haiku only for a literal
    re-fetch" — a seat the script never prints (ANGLES maps mechanical→haiku 1:1). The floor test
    reads `_floor()` alone and could not see it. Graded on the RENDERED span from the floor's own
    words to the pool-contract seam (= FLOOR + EXTRA_LIVE), comments stripped — the dispatch-step
    paragraph around it legitimately names Haiku for mechanical seats on OTHER surfaces."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    offenders, seen = [], set()
    for f in sorted(tmp_path.glob("*.md")):
        live = ac._HTML_COMMENT_RE.sub("", f.read_text())
        i = live.find("no mechanical seat")
        if i < 0:
            continue
        j = live.find("The pool contract is kept below", i)
        assert j > i, f.stem  # the seam bounds the span; a missing seam is its own defect
        seen.add(f.stem)
        if "haiku" in live[i:j].lower():
            offenders.append(f.stem)
    # the judgement floors BY NAME — a count with slack absorbed the loss of either of the
    # two round-7 kind changes (round-8 finding); `/fabrik-plan-review` moved to the SECTION-partition
    # kind (D-212/D-218), which names no mechanical seat and no Haiku seat at all
    assert seen >= {
        "fabrik-spec",
        "fabrik-vision",
        "fabrik-plan-after-chat",
        "fabrik-epics",
        "fabrik-conformance-review",
    }, seen
    assert "fabrik-plan-review" not in seen, seen
    assert offenders == [], offenders


# --- V7/V8 (T07) — the retired D-191 seat-mix literal, box-wide -----------------------------
#
# D-207 replaced the mix for the two partitioned review loops and D-208 rescoped the units-sized
# floor for every other command, so the retired sentence must survive NOWHERE that renders or
# prints. It hid in THREE wordings a line grep cannot see whole: the fragment's, the board
# banner's two adjacent string literals, and the rotation doc's line-wrapped one — hence the
# LINE-JOINED, case-insensitive read below, with a printed denominator (never a bare zero).

_RETIRED_LITERALS = (
    "one sonnet breadth seat and one haiku mechanical seat",
    "one sonnet + one haiku",
    # interpolation-tolerant: `_floor()` splits the sentence around `{native}`
    "breadth seat and one haiku mechanical seat per independent unit",
)


def _joined(text: str) -> str:
    """Line-joined, lower-cased — a wrapped or interpolated sentence reads as one string."""
    return " ".join(text.split()).lower()


def _v7_surface(tmp_path) -> dict[str, str]:
    """Every surface the retired literal could still render or print from, keyed by a readable
    name. `scripts/**/*.py` comes from `git ls-files` — a bare glob walks ~3,200 vendored files
    under the gitignored `scripts/kilo-benchmarks/.lcb-venv/`."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    files: dict[str, Path] = {f"rendered:{f.stem}": f for f in tmp_path.glob("*.md")}
    for f in (REPO / "commands" / "_sources").glob("*.md"):
        files[f"source:{f.stem}"] = f
    tracked = subprocess.run(
        ["git", "ls-files", "scripts"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.split()
    for rel in tracked:
        if rel.endswith(".py"):
            files[rel] = REPO / rel
    for f in (REPO / "docs" / "workstation").glob("*.md"):
        files[f"docs/workstation/{f.name}"] = f
    for rel in (
        "commands/_fragments/subagents-core.md",
        ".windsurf/rules/core/62-using-subagents.md",
        "CLAUDE.md",
        "templates/governance/CLAUDE.md",
        "docs/reference/convergence-prompts.md",
        "docs/reference/MD/ai-prompt-templates.md",
    ):
        files[rel] = REPO / rel
    return {name: p.read_text(errors="replace") for name, p in files.items()}


def test_v7_the_retired_d191_seat_mix_literal_survives_nowhere(tmp_path):
    surface = _v7_surface(tmp_path)
    assert len(surface) > 200, len(surface)  # the denominator this zero is measured against
    rendered = [n for n in surface if n.startswith("rendered:")]
    assert len(rendered) >= 30, len(rendered)
    carriers = {
        lit: sorted(n for n, t in surface.items() if lit in _joined(t)) for lit in _RETIRED_LITERALS
    }
    assert all(not v for v in carriers.values()), (
        f"{sum(len(v) for v in carriers.values())} of {len(surface)} files carry a retired "
        f"literal: {carriers}"
    )


def test_v7_the_units_sized_mix_keeps_its_scope_words_where_it_is_still_live():
    """The units-sized mix is NOT deleted — D-208 keeps it for every non-partitioned surface, so
    the absence check above must not be satisfiable by deleting the sentence. These are its
    positive controls: the script's own printed sentences and the two convergence docs."""
    printed = _joined((REPO / "scripts" / "sysadmin" / "dispatch_headroom.py").read_text())
    # T10 split the COST label by branch (`--mechanical 0` keeps the governance term "grounding
    # surface"; the default mix is "a surface with a mechanical angle") — the positive control
    # is the sentence stem plus the branch that keeps the term (merge-time seam, T10 before T07).
    assert "the maximum useful mix for a units-sized" in printed
    assert "grounding surface" in printed
    assert not [lit for lit in _RETIRED_LITERALS if lit in printed]
    for rel in (
        "docs/reference/convergence-prompts.md",
        "docs/reference/MD/ai-prompt-templates.md",
    ):
        assert "confirmed: 0" in (REPO / rel).read_text(), rel


_BANNER_PAYLOAD = {
    "caps": {"box_cap": 23, "concurrency_cap": 17},
    "box_caps": {"read_only": 23, "heavy": 12},
    "box_caps_floored": {"read_only": False, "heavy": False},
    "siblings": {"seats": 0, "ok": True},
    "quota": {"ok": True, "active": "a@x", "hottest_pct": 7.0, "eligible": 1},
}


def test_v7_the_rendered_board_banner_carries_no_retired_literal(tmp_path, monkeypatch):
    """`_budget_probe` swallows every exception into `Box budget unavailable: …`, so the positive
    control comes FIRST — an absence check against that fallback would pass vacuously."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    src = REPO / "scripts" / "sysadmin" / "quota_dashboard.py"
    spec = importlib.util.spec_from_file_location(f"qd_v7_{tmp_path.name}", src)
    qd = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(qd)

    class _Run:
        stdout = json.dumps(_BANNER_PAYLOAD)
        returncode = 0
        stderr = ""

    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _Run())
    html = qd._budget_probe()
    assert "Box budget (D-189" in html, html  # positive control: the real banner, not the fallback
    joined = _joined(html)
    assert not [lit for lit in _RETIRED_LITERALS if lit in joined], html


def test_v8_the_fragments_delta_round_sentence_survives_a_render(tmp_path):
    """The partition + delta-round rule lives in ONE fragment included by 20 sources; a render
    that drops it (an EXTRACT/PARAMS mismatch) leaves the two review loops with no seat rule."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    live = ac._HTML_COMMENT_RE.sub("", (tmp_path / "fabrik-review.md").read_text())
    assert "every later round is a DELTA over the fix diff" in live
    assert "--slices opus=N,sonnet=N,haiku=N" in live


_STRAY = b"\xff\xfe not utf8 \xff\n"


def _trees(tmp_path):
    return tmp_path, tmp_path / "_skills", tmp_path / "_agents"


def _census(tmp_path):
    d, s, a = _trees(tmp_path)
    # FILES only, and never through a link: a planted directory named SKILL.md (an abort fixture) or
    # a symlink to a file elsewhere is not a written wrapper. A (0, 0, 0) therefore proves no file
    # was written INSIDE the trees; a write THROUGH a link is proved by the target's content (the
    # symlink matrix asserts `theirs` survives), never by this count alone
    return (
        len([p for p in d.glob("*.md") if p.is_file() and not p.is_symlink()]),
        len(
            [
                p
                for p in s.glob("*/SKILL.md")
                if p.is_file() and not p.is_symlink() and not p.parent.is_symlink()
            ]
        ),
        len([p for p in a.glob("*.md") if p.is_file() and not p.is_symlink()]),
    )


def _defective_agent_sources(tmp_path, monkeypatch):
    src = tmp_path / "_agent_src"
    src.mkdir()
    for f in ac.AGENT_SRC.glob("*.md"):
        (src / f.name).write_text(f.read_text())
    first = sorted(src.glob("*.md"))[0]
    text = first.read_text()
    assert text.startswith("---\n")
    first.write_text(text.replace("---\n", "---\n\n", 1))  # a blank line inside the frontmatter
    monkeypatch.setattr(ac, "AGENT_SRC", src)


@pytest.mark.parametrize(
    "abort",
    [
        "over-cap NEXT",
        "defective agent source",
        "render error",
        "a file where a skill dir belongs",
        "the skills tree is a file",
        "SKILL.md is a directory",
        "a dangling symlink where a skill dir belongs",
        "the commands tree is a file",
        "the agents tree is a file",
        "a directory where a command file belongs",
        "a directory where an agent file belongs",
        "a broken symlink where a command file belongs",
        "a directory named like a command in the agents tree",
        "a directory named like a command in the commands tree",
        "an orphan skill whose SKILL.md is a directory",
    ],
)
def test_an_aborted_render_writes_into_none_of_the_three_trees(tmp_path, monkeypatch, abort):
    """Every render gate fires BEFORE the first write: an aborted render leaves the commands, skills
    AND agents trees exactly as it found them (Phase A heavy rounds 11–13: the cap raise sat inside
    the skills loop after all 36 commands were on disk; the agents tree was written before any gate;
    the defective-agent abort had no grader)."""
    if abort == "over-cap NEXT":
        monkeypatch.setitem(ac.NEXT, next(iter(ac.NEXT)), "x" * 1100)
        match = "composed skill description"
    elif abort == "defective agent source":
        _defective_agent_sources(tmp_path, monkeypatch)
        match = "blank line"
    elif abort == "render error":
        src = tmp_path / "_src"
        src.mkdir()
        for f in ac.SRC.glob("*.md"):
            (src / f.name).write_text(f.read_text())
        first = sorted(src.glob("*.md"))[0]
        first.write_text(first.read_text() + "\n{{include:nope}}\n")
        monkeypatch.setattr(ac, "SRC", src)
        match = r"^2$"  # the exit code itself, never a digit inside some other message
    else:
        d, s, a = _trees(tmp_path)
        name = next(iter(ac.NEXT))
        if abort == "a file where a skill dir belongs":
            s.mkdir()
            (s / name).write_text("a plain file where the skill DIRECTORY belongs")
        elif abort == "the skills tree is a file":
            s.write_text("a plain file where the skills TREE belongs")
        elif abort == "SKILL.md is a directory":
            (s / name / "SKILL.md").mkdir(parents=True)
        elif abort == "a dangling symlink where a skill dir belongs":
            s.mkdir()
            (s / name).symlink_to(tmp_path / "nowhere")
        elif abort == "the commands tree is a file":
            (tmp_path / "cmds").write_text("a plain file where the commands TREE belongs")
        elif abort == "a directory where a command file belongs":
            (d / f"{name}.md").mkdir(parents=True)
        elif abort == "a directory where an agent file belongs":
            (a / sorted(ac.AGENT_SRC.glob("*.md"))[0].name).mkdir(parents=True)
        elif abort == "a broken symlink where a command file belongs":
            d.mkdir(exist_ok=True)
            (d / f"{name}.md").symlink_to(tmp_path / "gone" / "target.md")
        elif abort == "a directory named like a command in the agents tree":
            (a / "zz-notasource.md").mkdir(parents=True)
        elif abort == "a directory named like a command in the commands tree":
            (d / "zz-notasource.md").mkdir(parents=True)
        elif abort == "an orphan skill whose SKILL.md is a directory":
            (s / "zz-orphan" / "SKILL.md").mkdir(parents=True)
        else:
            a.write_text("a plain file where the agents TREE belongs")
        tree_shapes = (
            "the skills tree is a file",
            "the commands tree is a file",
            "the agents tree is a file",
            "a file where a skill dir belongs",
            "a dangling symlink where a skill dir belongs",
        )
        leaf_noun = {
            "SKILL.md is a directory": "SKILL.md wrapper",
            "an orphan skill whose SKILL.md is a directory": "SKILL.md wrapper",
            "a directory where a command file belongs": "command file",
            "a broken symlink where a command file belongs": "command file",
            "a directory named like a command in the commands tree": "command file",
            "a directory where an agent file belongs": "agent file",
            "a directory named like a command in the agents tree": "agent file",
        }
        symlink_shapes = (
            "a dangling symlink where a skill dir belongs",
            "a broken symlink where a command file belongs",
        )
        if abort in symlink_shapes:
            match = "is a symlink"  # the ONE symlink rule, dangling or not
        elif abort in tree_shapes:
            match = "is not a directory"
        else:
            match = f"where the {leaf_noun[abort]} belongs"
    d, s, a = _trees(tmp_path)
    if abort == "the commands tree is a file":
        d = tmp_path / "cmds"
    with pytest.raises(SystemExit, match=match):
        ac.render(d, s, agents_dest=a)
    assert _census(tmp_path) == (0, 0, 0)


def test_the_floor_helper_refuses_an_unknown_kind():
    """A one-character slip in a PARAMS kind literal must never render the DEFAULT units-sized
    contract (with its Haiku seat) into a partitioned review — an unknown kind is loud."""
    with pytest.raises(ValueError, match="unknown floor kind"):
        ac._floor("section-partition", "`fabrik-reviewer`")


def test_a_preview_render_without_a_skills_tree_still_trips_the_cap(tmp_path, monkeypatch):
    """`render(dest)` (the `--dest /tmp/x` preview and the bare import form) composes the skill
    wrappers too, so a preview never reports success on a corpus the real render refuses."""
    monkeypatch.setitem(ac.NEXT, next(iter(ac.NEXT)), "x" * 1100)
    with pytest.raises(SystemExit, match="composed skill description"):
        ac.render(tmp_path, agents_dest=tmp_path / "_agents")
    assert _census(tmp_path) == (0, 0, 0)


def _installed(tmp_path, monkeypatch):
    """A clean install rendered into scratch trees, with `check()` pointed at them."""
    d, s, a = _trees(tmp_path)
    ac.render(d, s, agents_dest=a)
    monkeypatch.setattr(ac, "OUT", d)
    monkeypatch.setattr(ac, "SKILLS", s)
    monkeypatch.setattr(ac, "AGENTS", a)
    first_cmd = sorted(d.glob("*.md"))[0]
    first_agent = sorted(a.glob("*.md"))[0]
    return {
        "commands": (first_cmd, d / "zz-stray.md", d / "zz-orphan.md"),
        "skills": (
            s / first_cmd.stem / "SKILL.md",
            s / "zz-stray" / "SKILL.md",
            s / "zz-orphan" / "SKILL.md",
        ),
        "agents": (first_agent, a / "zz-stray.md", a / "zz-orphan.md"),
    }


def test_check_tolerates_a_non_utf8_stray_in_the_installed_trees(tmp_path, monkeypatch, capsys):
    """`check()` walks the INSTALLED trees with its own reads — a banner-less non-UTF-8 stray in any
    of the three must not crash the read-only gate (round 13; the agents tree in round 14)."""
    trees = _installed(tmp_path, monkeypatch)
    for _generated, stray, _orphan in trees.values():
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(_STRAY)
    ac.check()
    assert "check OK" in capsys.readouterr().out


@pytest.mark.parametrize("tree", ["commands", "skills", "agents"])
def test_check_reports_a_corrupted_installed_file_instead_of_crashing(
    tmp_path, monkeypatch, capsys, tree
):
    """A GENERATED installed file that acquired non-UTF-8 bytes (a bad-encoding hand edit, a truncated
    write) is reported as HAND-EDITED drift, never a traceback — for every installed tree, including the
    agents tree `agent_drift` reads first (round 14: that sixth read was still bare)."""
    generated, _stray, _orphan = _installed(tmp_path, monkeypatch)[tree]
    generated.write_bytes(_STRAY)
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 1
    assert "HAND-EDITED" in capsys.readouterr().out


@pytest.mark.parametrize("tree", ["commands", "skills"])
def test_check_reports_a_generated_orphan_in_the_installed_trees(
    tmp_path, monkeypatch, capsys, tree
):
    """An installed GENERATED command or skill whose source is gone is reported as an ORPHAN — the
    read-only mirror of the render prune (the agents tree has no orphan rule in `check()`)."""
    _generated, _stray, orphan = _installed(tmp_path, monkeypatch)[tree]
    orphan.parent.mkdir(parents=True, exist_ok=True)
    banner = ac.BANNER if tree == "commands" else ac.SKILL_BANNER
    orphan.write_text(banner + "\n# orphan\n")
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 1
    assert "ORPHAN" in capsys.readouterr().out


def test_every_render_prune_removes_a_generated_orphan_and_keeps_a_hand_authored_file(tmp_path):
    """The three render prunes, graded as one set: a banner-carrying orphan in each tree is removed,
    a banner-less file (hand-authored, or a non-UTF-8 stray) survives — the census alone cannot tell a
    working prune from a deleted one (round 14)."""
    d, s, a = _trees(tmp_path)
    (s / "zz-orphan").mkdir(parents=True)
    (s / "zz-stray").mkdir()
    a.mkdir()
    orphans = [d / "zz-orphan.md", s / "zz-orphan" / "SKILL.md", a / "zz-orphan.md"]
    for orphan, banner in zip(orphans, (ac.BANNER, ac.SKILL_BANNER, ac.BANNER), strict=True):
        orphan.write_text(banner + "\n# orphan\n")
    strays = [d / "zz-stray.md", s / "zz-stray" / "SKILL.md", a / "zz-stray.md"]
    for stray in strays:
        stray.write_bytes(_STRAY)
    ac.render(d, s, agents_dest=a)
    assert not any(orphan.exists() for orphan in orphans)
    assert all(stray.exists() for stray in strays)
    n_src, n_ag = len(list(ac.SRC.glob("*.md"))), len(list(ac.AGENT_SRC.glob("*.md")))
    assert _census(tmp_path) == (n_src + 1, n_src + 1, n_ag + 1)


def test_every_floor_kind_a_caller_passes_is_a_known_kind_and_nothing_more():
    """The guard is only as tight as its sets: the `_floor("…")` literals in the module ARE the union."""
    import ast

    tree = ast.parse(Path(ac.__file__).read_text())
    passed = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_floor"
        and isinstance(node.args[0], ast.Constant)
    }
    assert passed == set(ac._ALL_FLOOR_KINDS), passed ^ set(ac._ALL_FLOOR_KINDS)


def test_the_section_partition_floor_reaches_both_rendered_reviews(tmp_path):
    """The sentence D-212/D-218 added must reach the RENDERED spec and plan reviews — a FLOOR blanked
    at substitution time is invisible to the PARAMS-level test."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    for name in ("fabrik-spec-review", "fabrik-plan-review"):
        # the fragment carries {{FLOOR}} twice — live, and inside the POOL OFF comment — so the
        # assertion reads the LIVE text only, or a FLOOR blanked at substitution still "renders"
        live = re.sub(r"<!--.*?-->", "", (tmp_path / f"{name}.md").read_text(), flags=re.S)
        assert "cut into DISJOINT slices by SECTION" in live, name


def test_the_skills_prune_removes_only_the_generated_wrapper_and_never_through_a_symlink(tmp_path):
    """An orphan skill directory can hold hand-authored siblings (a reference file, a script) — the
    prune removes the banner-carrying SKILL.md and the directory only when that leaves it empty;
    a symlinked orphan is unlinked as a LINK, its target never touched."""
    d, s, a = _trees(tmp_path)
    orphan = s / "zz-retired"
    orphan.mkdir(parents=True)
    (orphan / "SKILL.md").write_text(ac.SKILL_BANNER + "\n# orphan\n")
    (orphan / "reference.md").write_text("hand-authored")
    real = tmp_path / "elsewhere"
    real.mkdir()
    (real / "SKILL.md").write_text(ac.SKILL_BANNER + "\n# linked orphan\n")
    (s / "zz-linked").symlink_to(real)
    ac.render(d, s, agents_dest=a)
    assert not (orphan / "SKILL.md").exists() and (orphan / "reference.md").exists()
    assert (real / "SKILL.md").exists() and not (
        s / "zz-linked"
    ).is_symlink()  # the LINK went, the target stayed


def test_an_orphan_skill_dir_holding_only_the_wrapper_is_removed_whole(tmp_path):
    d, s, a = _trees(tmp_path)
    orphan = s / "zz-retired"
    orphan.mkdir(parents=True)
    (orphan / "SKILL.md").write_text(ac.SKILL_BANNER + "\n# orphan\n")
    ac.render(d, s, agents_dest=a)
    assert not orphan.exists()


@pytest.mark.parametrize("tree", ["commands", "skills", "agents"])
def test_a_symlink_where_a_generated_path_belongs_is_refused_before_any_write(tmp_path, tree):
    """ONE symlink policy for the three trees (round 6 found the prune, the gate and the pre-flight
    disagreeing by shape and by tree): a symlink at a path the render would WRITE through is refused
    up front — the render never writes through a link, dangling or not."""
    d, s, a = _trees(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    name = next(iter(ac.NEXT))
    agent = sorted(ac.AGENT_SRC.glob("*.md"))[0].name
    if tree == "commands":
        (outside / f"{name}.md").write_text("theirs")
        (d / f"{name}.md").symlink_to(outside / f"{name}.md")
    elif tree == "skills":
        (outside / "SKILL.md").write_text("theirs")
        s.mkdir()
        (s / name).symlink_to(outside)
    else:
        (outside / agent).write_text("theirs")
        a.mkdir()
        (a / agent).symlink_to(outside / agent)
    with pytest.raises(SystemExit, match="symlink"):
        ac.render(d, s, agents_dest=a)
    assert _census(tmp_path) == (0, 0, 0)
    assert all(f.read_text() == "theirs" for f in outside.rglob("*.md"))


@pytest.mark.parametrize("tree", ["commands", "skills", "agents"])
def test_a_symlinked_orphan_is_reported_by_the_gate_and_unlinked_by_the_prune(
    tmp_path, monkeypatch, capsys, tree
):
    """A link in OUR tree is ours to remove, never to delete THROUGH: the gate reports a bannered
    symlinked orphan as an ORPHAN, the re-render it prescribes unlinks the LINK, the target survives,
    and the gate then reads OK — the same fixed point in every tree."""
    d, s, a = _trees(tmp_path)
    ac.render(d, s, agents_dest=a)
    outside = tmp_path / "outside"
    outside.mkdir()
    if tree == "commands":
        (outside / "zz-old.md").write_text(ac.BANNER + "\n# old\n")
        link = d / "zz-old.md"
        link.symlink_to(outside / "zz-old.md")
    elif tree == "skills":
        (outside / "SKILL.md").write_text(ac.SKILL_BANNER + "\n# old\n")
        link = s / "zz-old"
        link.symlink_to(outside)
    else:
        (outside / "zz-old.md").write_text(ac.BANNER + "\n# old\n")
        link = a / "zz-old.md"
        link.symlink_to(outside / "zz-old.md")
    monkeypatch.setattr(ac, "OUT", d)
    monkeypatch.setattr(ac, "SKILLS", s)
    monkeypatch.setattr(ac, "AGENTS", a)
    if tree != "agents":  # check() has orphan rules for the commands and skills trees
        with pytest.raises(SystemExit) as exc:
            ac.check()
        assert exc.value.code == 1 and "ORPHAN" in capsys.readouterr().out
    ac.render(d, s, agents_dest=a)
    assert not link.is_symlink() and not link.exists()
    assert list(outside.rglob("*.md"))  # the target survives
    ac.check()
    assert "check OK" in capsys.readouterr().out


@pytest.mark.parametrize("shape", ["a directory", "a broken symlink"])
def test_the_gate_reports_a_malformed_orphan_position_instead_of_crashing(
    tmp_path, monkeypatch, capsys, shape
):
    d, s, a = _trees(tmp_path)
    ac.render(d, s, agents_dest=a)
    monkeypatch.setattr(ac, "OUT", d)
    monkeypatch.setattr(ac, "SKILLS", s)
    monkeypatch.setattr(ac, "AGENTS", a)
    if shape == "a directory":
        (d / "zz-odd.md").mkdir()
        (s / "zz-odd" / "SKILL.md").mkdir(parents=True)
    else:
        (d / "zz-odd.md").symlink_to(tmp_path / "gone.md")
        (s / "zz-odd").mkdir()
        (s / "zz-odd" / "SKILL.md").symlink_to(tmp_path / "gone-too.md")
    with pytest.raises(SystemExit) as exc:
        ac.check()
    out = capsys.readouterr().out
    assert exc.value.code == 1 and out.count("not a regular file") == 2, out


def test_the_orphan_preflight_still_refuses_behind_a_symlinked_sibling(tmp_path):
    """The symlink skip in the orphan glob must `continue`, never `break`: a link that sorts first
    (the walk is sorted) must not hide a real directory where SKILL.md belongs behind it."""
    d, s, a = _trees(tmp_path)
    s.mkdir()
    (tmp_path / "elsewhere" / "SKILL.md").parent.mkdir()
    (tmp_path / "elsewhere" / "SKILL.md").write_text(
        "theirs"
    )  # a REAL target, so the glob visits the link
    (s / "aa-linked").symlink_to(tmp_path / "elsewhere")
    (s / "zz-broken" / "SKILL.md").mkdir(parents=True)
    with pytest.raises(SystemExit, match="SKILL.md wrapper belongs"):
        ac.render(d, s, agents_dest=a)
    assert _census(tmp_path) == (0, 0, 0)


def test_trees_that_are_symlinks_to_directories_are_a_legitimate_layout(tmp_path):
    """The no-symlink rule is for paths INSIDE the trees (the render never writes THROUGH a link to
    reach a generated file); an operator whose ~/.claude/commands, skills or agents is itself a
    symlink to a real directory is a layout, not a defect — the render lands in the target."""
    real = {k: tmp_path / f"real_{k}" for k in ("c", "s", "a")}
    for r in real.values():
        r.mkdir()
    d, s, a = tmp_path / "c", tmp_path / "s", tmp_path / "a"
    d.symlink_to(real["c"])
    s.symlink_to(real["s"])
    a.symlink_to(real["a"])
    ac.render(d, s, agents_dest=a)
    n_src, n_ag = len(list(ac.SRC.glob("*.md"))), len(list(ac.AGENT_SRC.glob("*.md")))
    assert (
        len(list(real["c"].glob("*.md"))),
        len(list(real["s"].glob("*/SKILL.md"))),
        len(list(real["a"].glob("*.md"))),
    ) == (n_src, n_src, n_ag)


@pytest.mark.parametrize("tree", ["commands", "skills", "agents"])
def test_a_dangling_orphan_link_survives_the_render_and_a_link_to_a_directory_is_left_alone(
    tmp_path, tree
):
    """The prunes read an orphan link only when it points at a FILE: a dangling `*.md` link (or a
    skill wrapper link gone stale under a symlinked parent) is left where it is, never a crash — and
    a link whose target is a DIRECTORY is neither read nor removed (round 7)."""
    d, s, a = _trees(tmp_path)
    ac.render(d, s, agents_dest=a)
    target_dir = tmp_path / "somedir"
    target_dir.mkdir()
    if tree == "commands":
        dangling, todir = d / "zz-dangle.md", d / "zz-todir.md"
    elif tree == "agents":
        dangling, todir = a / "zz-dangle.md", a / "zz-todir.md"
    else:
        linked = tmp_path / "linked"
        linked.mkdir()
        (linked / "SKILL.md").symlink_to(tmp_path / "gone.md")
        (s / "zz-link").symlink_to(linked)
        dangling = linked / "SKILL.md"
        (tmp_path / "linked2").mkdir()
        (tmp_path / "linked2" / "SKILL.md").symlink_to(target_dir)
        (s / "zz-link2").symlink_to(tmp_path / "linked2")
        todir = tmp_path / "linked2" / "SKILL.md"
    if tree != "skills":
        dangling.symlink_to(tmp_path / "gone.md")
        todir.symlink_to(target_dir)
    ac.render(d, s, agents_dest=a)
    assert dangling.is_symlink() and todir.is_symlink() and target_dir.is_dir()


@pytest.mark.parametrize("tree", ["commands", "agents"])
def test_the_prune_glob_preflight_still_refuses_behind_a_symlinked_sibling(tmp_path, tree):
    """The symlink skip in the commands/agents orphan globs must `continue`, never `break` — the
    walk is SORTED, so `aa-link.md` is visited first and a `break` there would hide `zz-dir.md`
    (an unsorted walk visited the directory first on one box and the link first on another, and
    the test passed either way: Finish round 8)."""
    d, s, a = _trees(tmp_path)
    t = d if tree == "commands" else a
    t.mkdir(exist_ok=True)
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "theirs.md").write_text(
        "theirs"
    )  # outside the commands tree (= tmp_path)
    (t / "aa-link.md").symlink_to(tmp_path / "elsewhere" / "theirs.md")  # sorts first
    (t / "zz-dir.md").mkdir()
    with pytest.raises(SystemExit, match="belongs"):
        ac.render(d, s, agents_dest=a)
    assert _census(tmp_path) == (0, 0, 0)


def test_a_directory_wrapper_behind_a_symlinked_orphan_dir_is_the_gates_not_the_preflights(
    tmp_path,
):
    """`entry.parent.is_symlink()` in the skills orphan glob: a DIRECTORY named SKILL.md inside a
    symlinked orphan skill dir is skipped by the pre-flight, left by the prune (not a file) and
    reported by the GATE for a hand removal — without that disjunct the render aborts with "is a
    directory where the SKILL.md wrapper belongs"."""
    d, s, a = _trees(tmp_path)
    s.mkdir()
    outside = tmp_path / "outside"
    (outside / "SKILL.md").mkdir(parents=True)
    (s / "zz-link").symlink_to(outside)
    ac.render(d, s, agents_dest=a)
    assert (s / "zz-link").is_symlink() and (outside / "SKILL.md").is_dir()


def test_an_orphan_fifo_never_hangs_the_render_or_the_gate(tmp_path, monkeypatch, capsys):
    """`is_file()` is the only read guard: a FIFO in an orphan position is neither read (a read would
    block forever) nor removed by the prune, and the gate reports it as not a regular file."""
    import os
    import signal

    if not hasattr(os, "mkfifo"):
        pytest.skip("no mkfifo on this platform")
    d, s, a = _trees(tmp_path)
    ac.render(d, s, agents_dest=a)
    os.mkfifo(d / "zz-fifo.md")
    (s / "zz-fifo").mkdir()
    os.mkfifo(s / "zz-fifo" / "SKILL.md")

    def _hang(signum, frame):
        raise TimeoutError("a read guard let a FIFO through — the render or the gate blocked on it")

    old = signal.signal(signal.SIGALRM, _hang)
    signal.alarm(20)
    try:
        ac.render(d, s, agents_dest=a)
        monkeypatch.setattr(ac, "OUT", d)
        monkeypatch.setattr(ac, "SKILLS", s)
        monkeypatch.setattr(ac, "AGENTS", a)
        with pytest.raises(SystemExit) as exc:
            ac.check()
        out = capsys.readouterr().out
        survived = (d / "zz-fifo.md").exists() and (s / "zz-fifo" / "SKILL.md").exists()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        # pytest keeps tmp dirs and nothing sweeps a FIFO left behind — remove BOTH on every path,
        # tolerating one a regressed prune already removed (the assertion below reports that)
        (d / "zz-fifo.md").unlink(missing_ok=True)
        (s / "zz-fifo" / "SKILL.md").unlink(missing_ok=True)
    assert survived, "a prune removed a FIFO it must not read"
    assert exc.value.code == 1 and out.count("not a regular file") == 2, out


def _reversed_glob(monkeypatch, tmp_path):
    """Force every `Path.glob` to yield in REVERSE sorted order: a walk the assembler wraps in
    `sorted()` still runs ascending, an unwrapped walk now runs descending — so a test's order
    claim no longer rides on what the filesystem happens to return (ext4 handed the round-8 seat and
    the orchestrator different orders for one fixture; here the order is forced). The fake is eager
    (a list; no caller passes `case_sensitive=`) and PROVES ITSELF on a probe dir before it is
    trusted: the whole kill power of the two order tests is `reverse=True`, so losing it must fail
    them, not silently pass them."""
    real = Path.glob
    monkeypatch.setattr(Path, "glob", lambda self, pat: sorted(real(self, pat), reverse=True))
    # the probe sits INSIDE the commands tree (`_trees` returns `tmp_path` itself): four bare names
    # no `*.md` or `*/SKILL.md` glob matches — invisible to the render, the pre-flight and
    # `_census` — and four rather than two so a filesystem whose raw order happens to be
    # descending cannot pass a fake that reverses nothing (1 in 24, not 1 in 2)
    probe = tmp_path / "_glob-probe"
    probe.mkdir(exist_ok=True)
    for name in ("a", "b", "c", "d"):
        (probe / name).touch()
    assert [p.name for p in probe.glob("*")] == ["d", "c", "b", "a"], "the fake is not reversing"


@pytest.mark.parametrize("tree", ["commands", "skills", "agents"])
def test_the_preflight_names_the_first_offender_in_sorted_order(tmp_path, monkeypatch, tree):
    """The orphan globs are `sorted()`: two offenders, the refusal names the one that sorts first —
    under a reversed `Path.glob` an unsorted walk would name the other — and, like every abort,
    nothing was written."""
    d, s, a = _trees(tmp_path)
    t = {"commands": d, "agents": a, "skills": s}[tree]
    t.mkdir(exist_ok=True)
    if tree == "skills":
        (s / "aa-x" / "SKILL.md").mkdir(parents=True)
        (s / "zz-x" / "SKILL.md").mkdir(parents=True)
    else:
        (t / "aa-dir.md").mkdir()
        (t / "zz-dir.md").mkdir()
    _reversed_glob(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match=r"aa-(dir\.md|x)"):
        ac.render(d, s, agents_dest=a)
    assert _census(tmp_path) == (0, 0, 0)


@pytest.mark.parametrize("tree", ["commands", "skills", "agents"])
def test_the_prune_walks_in_sorted_order_so_a_link_that_sorts_first_goes_before_its_target(
    tmp_path, monkeypatch, tree
):
    """The prunes are `sorted()`: an orphan LINK whose name sorts BEFORE its bannered orphan
    TARGET's is unlinked first (it still resolves), then the target — for that pair nothing dangles.
    Under a reversed `Path.glob` an unsorted walk removes the target first and leaves the link
    dangling forever. The sorted walk is DETERMINISTIC, not dangle-free: a link whose name sorts
    AFTER its target's still dangles (the Finish receipt's row M6; the interlinked-links item of
    the assembler's row in `docs/STRATEGIC_BACKLOG.md`)."""
    d, s, a = _trees(tmp_path)
    ac.render(d, s, agents_dest=a)
    if tree == "skills":
        (s / "zz-t").mkdir()
        (s / "zz-t" / "SKILL.md").write_text(ac.SKILL_BANNER + "\n# t\n")
        link, target = s / "aa-link", s / "zz-t"
    else:
        t = d if tree == "commands" else a
        (t / "zz-target.md").write_text(ac.BANNER + "\n# t\n")
        link, target = t / "aa-link.md", t / "zz-target.md"
    link.symlink_to(target)
    _reversed_glob(monkeypatch, tmp_path)
    ac.render(d, s, agents_dest=a)
    assert not link.is_symlink() and not link.exists() and not target.exists()


def test_a_symlinked_orphan_wrapper_file_is_unlinked_not_refused(tmp_path):
    """`tests/test_assemble_orch_retired.py` plants a retired skill whose SKILL.md is a symlink: an
    orphan LINK to a bannered file is the prune's to unlink, never the pre-flight's to refuse."""
    d, s, a = _trees(tmp_path)
    ac.render(d, s, agents_dest=a)
    outside = tmp_path / "outside" / "SKILL.md"
    outside.parent.mkdir()
    outside.write_text(ac.SKILL_BANNER + "\n# retired\n")
    (s / "zz-retired").mkdir()
    (s / "zz-retired" / "SKILL.md").symlink_to(outside)
    ac.render(d, s, agents_dest=a)
    assert not (s / "zz-retired" / "SKILL.md").is_symlink() and outside.exists()


def test_the_finish_docs_review_skips_docs_the_heavy_review_graded(tmp_path):
    """Spec D9 (review-family pass 3): the Finish `/fabrik-docs-review` runs over the plan's changed
    docs MINUS those the whole-plan `/fabrik-review` receipt graded, and records `SKIPPED — …` when
    the set is empty. A text-presence grader — `check_plan_quality.py` reads no Execution notes, so
    the behaviour itself is observed by the spec's V6, never enforced here."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    text = (tmp_path / "fabrik-execute-plan.md").read_text()
    assert "MINUS the docs the whole-plan" in text
    assert text.count("SKIPPED — every changed doc was review surface") >= 2  # the rule + the loop


def test_the_four_fragment_less_loops_now_include_the_termination_fragment(tmp_path):
    """D1 (review-family pass 3): `/fabrik-docs-review`, `/fabrik-rules-review`, `/fabrik-epics-review`
    and `/design-review` include `term-edit` with every slot filled; `/fabrik-review-scoped` cites it
    and stays receipt-less. Graded on the SOURCES and on the rendered slots (an unfilled slot is a
    render refusal, which `--check` already proves)."""
    src = REPO / "commands" / "_sources"
    for name in (
        "fabrik-docs-review",
        "fabrik-rules-review",
        "fabrik-epics-review",
        "design-review",
    ):
        assert "{{include:term-edit}}" in (src / f"{name}.md").read_text(), name
        assert set(ac.PARAMS[name]["term-edit"]) == {
            "ARTIFACT",
            "DONE_ACT",
            "DONE_WORD",
            "AXES",
            "EXEMPT_NOTE",
        }, name
    assert "{{include:term-edit}}" not in (src / "fabrik-review-scoped.md").read_text()
    assert "{{include:term-coverage}}" not in (src / "fabrik-review-scoped.md").read_text()
    consumers = sorted(p.stem for p in src.glob("*.md") if "{{include:term-edit}}" in p.read_text())
    assert len(consumers) == 17, consumers
