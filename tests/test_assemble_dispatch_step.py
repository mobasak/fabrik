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
    assert examined == sum(len(p) for p in ac.EXTRACT.values()), (
        examined
    )  # every entry, none skipped
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
        for native in ("`fabrik-reviewer`", "`fabrik-researcher`")
    }
    assert units == {
        "`fabrik-reviewer`": ["fabrik-doc-converge", "fabrik-features"],
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
