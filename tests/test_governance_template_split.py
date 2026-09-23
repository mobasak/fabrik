# AFTER-EDIT: scripts/fabrik_synced_manifest.py, scripts/sync_enforcement_to_projects.py
"""Shared governance-contract invariants across the hub CLAUDE.md, the fleet template and
fabrik-lib's hand-kept copy.

Four concerns live here, each in its own banner-marked block:
  * the hub/project SPLIT — the fleet template is sourced from templates/governance/CLAUDE.md,
    never from the hub's own /opt/fabrik/CLAUDE.md, which is the HUB agents' contract and is not
    distributed (plan 2026-08-08-plan-1-claude-md-hub-split.md, Phase A);
  * T6 — the shared-tree commit rules, pinned by claim so they cannot diverge between copies;
  * the QUOTA bands and the QUOTA line, graded identical across all three contracts;
  * T04a — the /fabrik-task LANE TABLE in CLAUDE.md § Orient step 0, graded against the SIZE
    gate's own constants and evaluation order (plan 2026-09-18-plan-1-fabrik-task-lane).
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from pathlib import Path

import pytest

FABRIK = Path(__file__).resolve().parents[1]
TEMPLATE_REL = "templates/governance/CLAUDE.md"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, FABRIK / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(FABRIK / "scripts"))
    sys.modules[name] = mod  # dataclass decoration resolves cls.__module__ here
    try:
        spec.loader.exec_module(mod)
    except Exception:
        # CPython's own loader pops the entry on exec failure; this hand-rolled one did not,
        # leaving a HOLLOW module that a later plain import returns with no ImportError.
        sys.modules.pop(name, None)
        raise
    return mod


manifest = _load("fabrik_synced_manifest", "scripts/fabrik_synced_manifest.py")


def _tmp_fabrik(tmp_path: Path) -> Path:
    """A minimal fabrik root carrying only the fixture template."""
    root = tmp_path / "fabrik"
    (root / "templates/governance").mkdir(parents=True)
    (root / TEMPLATE_REL).write_text("# fixture template\n", encoding="utf-8")
    return root


def test_manifest_lists_template_not_governance_file() -> None:
    assert "CLAUDE.md" not in manifest.GOVERNANCE_FILES
    assert manifest.GOVERNANCE_TEMPLATES == [
        (TEMPLATE_REL, "CLAUDE.md"),
        # decision-ledger seed (SEED_IF_MISSING class — copied once when absent, then
        # project-owned; plan-1 2026-08-30)
        ("templates/governance/DECISIONS.md", "docs/DECISIONS.md"),
        # worktree-copy manifest (plan 2026-09-03-plan-1-multi-agent-per-repo, T01a)
        ("templates/governance/.worktreeinclude", ".worktreeinclude"),
    ]


def test_iter_synced_pairs_yields_template_sourced_claude(tmp_path: Path) -> None:
    fabrik_root = _tmp_fabrik(tmp_path)
    proj = tmp_path / "proj"
    proj.mkdir()
    pairs = list(manifest.iter_synced_pairs(proj, fabrik_root))
    claude_pairs = [(s, d) for s, d in pairs if d.name == "CLAUDE.md"]
    assert claude_pairs == [(fabrik_root / TEMPLATE_REL, proj / "CLAUDE.md")]
    assert all(s != fabrik_root / "CLAUDE.md" for s, _ in pairs), (
        "the hub's own CLAUDE.md must never be a sync source"
    )


def test_sync_dry_run_sources_claude_from_template(tmp_path: Path, monkeypatch) -> None:
    sync = _load("sync_enforcement_to_projects", "scripts/sync_enforcement_to_projects.py")
    fabrik_root = _tmp_fabrik(tmp_path)
    monkeypatch.setattr(sync, "FABRIK_ROOT", fabrik_root)
    proj = tmp_path / "proj"
    proj.mkdir()
    result = sync.sync_scripts_to_project(proj, dry_run=True)
    claude_results = [r for r in result.files if r.destination.name == "CLAUDE.md"]
    assert claude_results, "sync must consider CLAUDE.md"
    assert all("templates/governance" in str(r.source) for r in claude_results), (
        f"CLAUDE.md must be template-sourced, got: {[str(r.source) for r in claude_results]}"
    )


def test_gitignore_block_still_ignores_claude() -> None:
    # The fleet .gitignore "Fabrik-synced" block derives from NAME LISTS, not
    # iter_synced_pairs — template-sourced dests must be fed in explicitly.
    # (Live regression: removing CLAUDE.md from GOVERNANCE_FILES silently
    # dropped its ignore line fleet-wide on the next sync.)
    assert "CLAUDE.md" in manifest.gitignore_block_text()
    assert "CLAUDE.md" in manifest.gitignore_dest_paths()["Governance files"]


def test_precommit_filter_watches_template_not_hub_file() -> None:
    # Guard the trigger swap: template edits fire the fleet sync, hub-contract
    # edits do not (revert of the swap must red this).
    cfg = (FABRIK / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "^templates/governance/" in cfg
    assert "^CLAUDE\\.md$" not in cfg


def test_scaffold_seeds_claude_from_template() -> None:
    # Unit-level source guard (no full scaffold run): the G-B5 copy must read the
    # template path, not the hub's contract.
    sys.path.insert(0, str(FABRIK / "src"))
    from fabrik import scaffold  # noqa: PLC0415

    src = inspect.getsource(scaffold._scaffold_shared)
    assert 'FABRIK_ROOT / "templates/governance/CLAUDE.md"' in src
    assert 'FABRIK_ROOT / "CLAUDE.md"' not in src


# ── T6: the shared-tree commit rules must reach the fleet, not just the hub ────────────────────

# The three sentences Phase C adds (T6.1–T6.3). They are quoted by a distinctive fragment rather
# than in full: the surrounding prose is edited often, the CLAIM is what must not diverge. Each was
# EXECUTED before it was written (2026-09-14, scratch repo) — a remedy written from reasoning is how
# a two-operand `test -f` and a nonexistent heading reached this plan's own review.
T6_CLAIMS = (
    # T6.1 (01M2803TM) — the omission direction.
    "A LITERAL file path git does not track fails LOUDLY",
    "a DIRECTORY or a QUOTED GLOB pathspec is silent",
    # T6.2 (01M1RGRVT, 01M1RHJEY) — the private-index recipe. Round 1 fixed a vacuous CAS; round 2
    # fixed four steps that were wrong when executed; round 3 fixed four more the edges exposed.
    "**A pathspec protects the FILE LIST, never the CONTENT.**",
    "The last argument is the expected OLD value and it MUST be the captured `$base`.",
    "the `env -u` is load-bearing",
    # T6.3 (fabrik-lib 01M2JZC35M5K9V7XWMCMA5GM4W, 2026-09-16) — step 7 warned what happens if the
    # carry is SKIPPED but pointed at no guard, so a just-committed row sat in the working tree as a
    # pending DELETION and the next pathspec commit would have removed it. Measured twice in one run.
    "Then run step 5b's guard",
    # D-284 (2026-09-17) — the pytest leg's semantics have ONE prose home: the GATE row's shared
    # sentence cites the arming conjunction and names the three `--json` keys; a commit message
    # claimed this grader proved the two copies identical when it asserted nothing about the
    # sentence (scoped review seat C) — now it does, on a span no other clause repeats.
    "cited because the paraphrase drifted once (",
    "in a Tier-2 run (the default tier — only `--lean`/`--systemic` change it, `:2914-2920`)",
    "the rows that can never fail — `WARN_ONLY_CHECKS`, `:335-348` — carrying each one's own text",
    "only a leg that ran to completion is the bare `pytest`",
    "`skipped_checks` (bare NAMES — both rows reduce to `pytest` there, never the reason) AND `advisory`",
    "a `status: \"setup-error\"` envelope (`:2896-2912` — the `REQUIRED_TOOLS` probe, ruff OR pytest missing, before any tier runs) carries none of these keys",
    "FROM THE REPO ROOT",
    # Round 2: the un-discriminated wording FALSE-ALARMED on a CORRECT CHANGELOG.md carry — the
    # scratch blob is built with `>>` at EOF per step 2 while step 7 places the hunk atop
    # [Unreleased], which is a `-`/`+` PAIR and loses nothing. Executed in a throwaway repo, and
    # reverting it failed 0 of the other 18 claims.
    "sanctioned `CHANGELOG.md` relocation, not a loss",
    # T6.4 (operator directive 01M2K9JZNG4Y6110629YZGA65A, 2026-09-16) — the quota BANDS are a
    # behaviour contract, and they live INSIDE the D-175 quota bullet that teaches the read.
    # AMBER forbids STARTING heavy work rather than ordering a compaction, because a compaction
    # that no flip follows costs more than it saves. ⚠️ The tick-row counts this comment used to
    # quote are DELETED: D-264 records them as refuted (a wrong-window artefact), and they were the
    # last surviving copy of the very claim the contract paragraph forbids re-deriving.
    "THE QUOTA BANDS ARE A BEHAVIOUR CONTRACT",
    # the BOUNDARIES themselves, not just the heading: the bands were edited three times in one
    # session and twice landed wrong (an overlap at 90, then a hole at 90), so the strings a
    # one-sided hub edit would break are pinned here rather than trusted to review.
    # ⚠️ WRAP-SAFE substrings only — these must never span a line break. The first cut pinned
    # "**85 to under 90 — AMBER" and "**90 and over —", and the very next rewrite of the bullet
    # rewrapped both across lines, so the pins stopped matching and the test went red on text that
    # was actually correct. Pin a fragment that lives on ONE line.
    # T6.5 (2026-09-17) — the revert-test recipe never asked who else is READING the file, and the
    # first cut of the fix was NOT EXECUTABLE: it said to copy the FILE, which makes every grader
    # (they resolve their subject by tree path) run against the unmutated original and print a FALSE
    # GREEN — the outcome the surrounding sentences exist to prevent. It shipped to 45 repos before a
    # seat executed it. These pins are why the second cut cannot drift or vanish from one copy.
    # ⚠️ WRAP-SAFE: each must live on ONE line of the contract (see the note above).
    "never on a single copied FILE",
    "it can reach committed state",
    "treat the condition as TRUE by default",
    # D-299: the lines are the WALL's, so the anchors are the runway phrases, not percentages
    "more than 5 points of runway — GREEN",
    "5 points or fewer",
    "RED: commit, push, close your run record",
    "COMPACTION IS CONDITIONAL",
    "follow it with a real `unset GIT_INDEX_FILE`",
    "never `cp <scratch>/<file> <file>`",
    "never put the hunk in printf's FORMAT position",
    'Assert `git diff-index --cached --numstat "$base"` is YOUR hunk alone',
    "On rc 128 your work is not lost and the fix is not to weaken the guard",
    "their commit is in HEAD but NOT in your working file",
    "no COMMIT hook runs",
    "Count it git-aware",
    # T6.3 (01M20DXPT) — `0 0` is a verdict about LINES.
    "Two different questions, two different expectations",
    # Round 2: the bullet's opening line and the HARD STOPS row mandated the guard the pathspec
    # rule forbids. All three sit in one single-line bullet where no reader sees them together.
    "`git diff --cached --name-only` when you STAGED it, `git diff HEAD -- <paths>` when you are "
    "committing by PATHSPEC",
    "`git diff --cached --name-only` for a STAGED commit, `git diff HEAD -- <paths>` for a PATHSPEC "
    "commit",
)


def test_the_shared_tree_commit_rules_are_identical_in_both_contracts() -> None:
    """T6 Behavior Contract: the hub's CLAUDE.md and the fleet template carry the same three
    sentences, byte for byte.

    The two files are deliberately NOT byte-identical overall — the hub's is the hub agents' own
    contract — so nothing binds a shared rule across them except a grader like this one. A rule
    added to the hub file alone reaches three sessions; the same rule in the template reaches ~46
    repos on the next governance sync, and the failure mode is silent: the hub agent who wrote it
    reads it every session and never notices the fleet does not have it."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    template = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    missing = [
        (c[:48], hub.count(c), template.count(c))
        for c in T6_CLAIMS
        if hub.count(c) != 1 or template.count(c) != 1
    ]
    assert not missing, f"claim | hub count | template count -> {missing}"


def test_the_governance_files_are_on_the_sync_trigger_path() -> None:
    """A T6 sentence in the template is inert until a commit distributes it, and the trigger set is
    the `governance-sync` files-filter in `.pre-commit-config.yaml` — read, never recalled
    (CLAUDE.md § Sync-consciousness). This asserts the template is matched by that regex, so the
    three sentences actually leave this repo."""
    import re

    cfg = (FABRIK / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    block = cfg.split("id: governance-sync", 1)
    assert len(block) == 2, "the governance-sync hook is gone — the trigger set moved"
    m = re.search(r"^\s*files:\s*(?:\|-?\s*\n\s*)?(.+)$", block[1], re.MULTILINE)
    assert m, "the governance-sync hook has no files: filter"
    pattern = m.group(1).strip().strip("'\"")
    assert re.search(pattern, TEMPLATE_REL), (pattern, TEMPLATE_REL)


# --- Phase A of docs/development/plans/2026-09-16-plan-1-quota-posture.md (D-269) ---------------
THIRD_CONTRACT = Path("/opt/fabrik-lib/CLAUDE.md")

# The quota BANDS (D-265) and the QUOTA line (D-269) live INSIDE the D-175 quota bullet of all THREE
# contracts — the hub's own, the template that reaches ~46 repos, and the sync-excluded
# fabrik-lib's hand-kept copy, which was measured one version behind on 2026-09-16. Short substrings
# of the shared sentences; counted on whitespace-normalised text because the hub and the template
# hard-wrap the bullet at ~93-96 columns while fabrik-lib keeps it on one line.
QUOTA_CLAIMS = (
    "**more than 5 points of runway — GREEN:**",
    "5 points or fewer",
    "RED: commit, push, close your run record",
    "posture unavailable",
    # ⚠️ re-pinned 2026-09-17 on the operator's ruling: the hold is FLEET-aware, so the claim must
    # carry the precondition. Pinning the bare "at RED the hook HOLDS" would let a contract that
    # dropped the successor caveat pass — which is the version that stopped agents while eligible
    # accounts sat in the queue.
    "at RED the hook HOLDS `Agent` and a new",
    # T6.6 (operator ruling 2026-09-17) — the band is the FLEET's, per window. A contract that
    # slid back to a per-account band, or one that let agents re-derive it from the percentages,
    # is the version that stopped agents while fresh accounts sat in the queue.
    "FLEET'S, computed per window, never one account's",
    # T6.7 (2026-09-17, 01M2P42QZMTX8RAQ24SCV45VSY) — the LINE explains its own band, because the
    # contract cannot reach a session that loaded the old table hours ago.
    "**The `QUOTA:` line (D-269, D-275).**",
    "Read the line, not the arithmetic.",
    "account alone reads <band>; the band is the fleet's, act on it]",
    "Never re-derive the band from the percentages",
    "a `successor` still named is a",
    "is banded on its Fable window too",
    "is the authority on WHEN you resume, in every band",
    # Delta 9 seat C — the line can print a token the contracts never described.
    "nobody serves it` inside the parenthesis",
    "joined as `on 5h and weekly`, when neither is served",
)


def _normalised(path: Path) -> str:
    import re

    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def test_the_quota_bands_and_the_quota_line_are_identical_in_all_three_contracts() -> None:
    """Each QUOTA claim appears exactly once in the hub file, the template AND fabrik-lib's contract.

    fabrik-lib is sync-excluded and hand-maintained, so nothing but a grader like this one binds a
    shared sentence across it and the hub (it carried D-264's `85-90` / `90+ with NO eligible
    successor` text for a day after the hub moved to D-265). The third file is skipped with a
    stated reason when it is not checked out, so the suite stays portable.
    """
    hub = _normalised(FABRIK / "CLAUDE.md")
    template = _normalised(FABRIK / TEMPLATE_REL)
    missing = [
        (c[:48], hub.count(c), template.count(c))
        for c in QUOTA_CLAIMS
        if hub.count(c) != 1 or template.count(c) != 1
    ]
    assert not missing, f"claim | hub count | template count -> {missing}"
    if not THIRD_CONTRACT.exists():
        import pytest

        pytest.skip("fabrik-lib is not checked out on this box — the third-file half is ungraded")
    third = _normalised(THIRD_CONTRACT)
    missing3 = [(c[:48], third.count(c)) for c in QUOTA_CLAIMS if third.count(c) != 1]
    assert not missing3, f"claim | fabrik-lib count -> {missing3}"


# The two shared spans, extracted from the NORMALISED text: the D-269 sentence set and the D-265
# resume-authority sentences. Anchors are the spans' own first and last words, so a wrap boundary
# inside either span is not a miss.
_SHARED_SPANS = (
    r"\*\*The `QUOTA:` line \(D-269, D-275\)\.\*\*.*?the hottest of 5h, weekly and Fable\.",
    r"`claude_rotate\.py --status` is the authority on WHEN you resume.*?read `--status` rather than assuming\.",
    # D-295: the Fable clamp is the ONE place a band is not the fleet's, so the sentences that say
    # so are graded three-way identical like every other shared QUOTA span. Pinned as its OWN span
    # rather than by widening the first: that one ends on `the hottest of 5h, weekly and Fable.`,
    # and extending the wording past that period silently unanchors it (measured — the first cut of
    # this change did exactly that and `_shared_spans` reported the span MISSING, not drifted).
    r"THAT LAST ONE IS THE SINGLE PLACE A BAND IS NOT THE FLEET'S.*?never a wait \(D-295\)\.",
    # D-306: the stamp's two tiers are a BEHAVIOUR claim — only `walled` holds — so the sentences
    # that say so are graded three-way like every other shared QUOTA span. Pinned as its OWN span
    # with fresh endpoints, never by widening a neighbour: the span above ends on
    # `never a wait (D-295).`, and rewording past that period unanchors it, which the grader
    # reports as MISSING (a deleted sentence) rather than as drift. Measured 2026-09-18 on the
    # D-295 carve-out; the memory note `extending-a-sentence-unanchors-its-pinned-span` carries it.
    # ⚠️ fabrik-lib carried the PRE-D-306 wording for a day after the hub moved — exactly the drift
    # this file exists to catch, and nothing caught it because the paragraph was unpinned.
    r"⚠️ THE STAMP HAS TWO TIERS AND ONLY THAT ONE HOLDS \(D-306\)\..*?only the wall is a wall\.",
)


def _shared_spans(text: str) -> tuple[str, ...]:
    import re

    found = tuple(m.group(0) if (m := re.search(p, text)) else "" for p in _SHARED_SPANS)
    assert all(found), f"a shared span is missing from a contract: {[bool(f) for f in found]}"
    return found


def test_the_quota_line_sentence_set_is_identical_across_the_three_contracts() -> None:
    """A1b: the shared spans are IDENTICAL (after whitespace normalisation) in all three contracts.

    The eight-anchor count above catches a sentence that went missing; only this grader catches a
    format token, a band name or an action that DRIFTED in one file while every anchor still counts
    one — which is what the contract's carve-out claims is graded. The third file skips as above.
    """
    hub = _shared_spans(_normalised(FABRIK / "CLAUDE.md"))
    template = _shared_spans(_normalised(FABRIK / TEMPLATE_REL))
    assert hub == template, "the hub and the template drifted on a shared QUOTA span"
    if not THIRD_CONTRACT.exists():
        import pytest

        pytest.skip("fabrik-lib is not checked out on this box — the third-file half is ungraded")
    assert _shared_spans(_normalised(THIRD_CONTRACT)) == hub, (
        "fabrik-lib drifted on a shared QUOTA span"
    )


def test_the_third_contract_half_skips_with_a_reason_when_fabrik_lib_is_absent(
    monkeypatch, tmp_path
) -> None:
    """A2: the hub/template half still grades when the third file is missing; the skip names why."""
    import pytest

    monkeypatch.setitem(globals(), "THIRD_CONTRACT", tmp_path / "absent" / "CLAUDE.md")
    with pytest.raises(pytest.skip.Exception) as excinfo:
        test_the_quota_bands_and_the_quota_line_are_identical_in_all_three_contracts()
    assert "not checked out" in str(excinfo.value)


# ── T04a: the /fabrik-task lane table in § Orient step 0 ───────────────────────────────────────
# docs/development/plans/2026-09-18-plan-1-fabrik-task-lane/T04a-hub-claude-md.md, implementing
# docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md § The decision rule (D-289/D-291/
# D-292). The six tests decide the LANE before any drafting, and the table is the only place the
# five `--declare` answers `/fabrik-task` asks for are defined — `commands/_sources/fabrik-task.md`
# sends the agent here by name, so a missing or renamed table breaks the command it documents.
# Hub-only for now; T04b mirrors it into templates/governance/CLAUDE.md for the ~46 repos.
_STEP0_START = "0. **Task→skill routing:**"
_STEP0_END = "1. **Hub identity, not a scaffold type:**"
# The template is a PROJECT contract: its step 1 is the scaffold type, not the hub identity, so
# the section's lower bound differs and the hub's anchor would never match (the END guard caught
# this the moment the mirror landed — which is the guard working, not a defect in it).
_STEP0_END_TPL = "1. `project.yaml::type` tells you which"
# The pointer the two sizing clauses collapse to (operator ruling U19) — it names the table by the
# heading and the noun, so both must survive a rewording of either.
_LANE_POINTER = "SIZE it against § Orient step 0's lane table"
# The enumeration the HANDLE-NOW clause drops: it stated a SECOND, DIFFERENT test (>5 files, and a
# vendored/synced surface routed to SPEC/PLAN work where rule 1 routes a sync path to right-now +
# the full /fabrik-review — the opposite disposition). Two sources of truth for one decision.
_OLD_INLINE_TEST = "(a new mechanism, a vendored/synced surface, schema, auth, >5 files)"


def _delim_row():
    """The GFM delimiter regex, LOADED from the checker that owns it rather than hand-copied.

    Deliberately function-scoped: at module scope a rename of that script or of its private
    `_DELIM` aborts COLLECTION of this whole file — all 17 tests — instead of reddening only the
    4 that call it. Measured both ways: a renamed script and a renamed symbol each red exactly 4."""
    return _load("check_governance_tables",
                 "scripts/enforcement/check_governance_tables.py")._DELIM


def _step0_body(text: str, end: str = _STEP0_END) -> str:
    """§ Orient step 0, bounded at BOTH ends.

    ⚠️ A missing START raises IndexError (loud); a missing END does NOT raise — `split` on an
    absent separator returns the whole remaining string — so the section silently grows to the end
    of a 130 KB file and every `in step0` check passes from anywhere in the document. The first cut
    of this guard protected one of the two split sites; the other kept the unbounded shape."""
    assert text.count(_STEP0_START) == 1, f"§ Orient step-0 START anchor drifted: {_STEP0_START!r}"
    assert text.count(end) == 1, f"§ Orient step-0 END anchor drifted: {end!r}"
    return text.split(_STEP0_START, 1)[1].split(end, 1)[0]


def _step0_tables(text: str, end: str = _STEP0_END) -> list[list[list[str]]]:
    """Every markdown table inside § Orient step 0, as rows of stripped cells.

    ⚠️ A pure EXTRACTOR. It does not decide whether a table is valid GFM — three rounds of
    hand-rolling that (indent width, tab expansion, "was a delimiter row seen") produced both
    false NEGATIVES (a delimiter row one cell short renders nothing and passed) and false
    POSITIVES (a GFM-legal delimiter row may omit either outer pipe, and a fenced code example
    containing a pipe row is not a table at all — both reddened four tests on correct markdown).
    Validity is now decided by an actual renderer in
    `test_the_lane_table_renders_as_a_table_for_every_gfm_reader`, which cannot disagree with GFM
    because it IS GFM."""
    body = _step0_body(text, end)
    delim = _delim_row()
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for raw in body.split("\n"):
        line = raw.strip()
        if line.startswith("|") and line.endswith("|"):
            if delim.match(line):
                continue
            current.append([c.strip() for c in line.strip("|").split("|")])
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _lane_table(text: str, end: str = _STEP0_END) -> list[list[str]]:
    """The lane table specifically — identified by its header, not by its rows' first cells."""
    lane = [t for t in _step0_tables(text, end) if t and t[0][:2] == ["#", "Test"]]
    assert len(lane) == 1, (
        f"expected exactly one lane table in step 0, found {len(lane)}. House convention: every "
        "governance-table row carries BOTH outer pipes — `scripts/enforcement/check_governance_"
        "tables.py` uses the same startswith/endswith rule, so a row missing one is invisible to "
        "the fleet check too (executed). GFM itself would accept it; we do not."
    )
    return lane[0]


def test_the_lane_table_carries_the_six_tests_and_its_verdict_row() -> None:
    """T04a Behavior Contract: § Orient step 0 carries the lane table.

    Red-first note: watched RED before the table existed — step 0 then held only the stage table,
    whose first column carries stage names, not test numbers, so `_lane_table` raised."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    rows = _lane_table(hub)[1:]  # drop the header
    assert [r[0] for r in rows] == ["1", "1b", "2", "3", "4", "4b", "5", "6"], [r[0] for r in rows]
    header = _lane_table(hub)[0]
    wrong = [r[0] for r in rows if len(r) != len(header)]
    assert not wrong, f"rows whose cell count != the header's {len(header)}: {wrong}"


def test_the_lane_tables_verdict_row_names_a_command_that_exists() -> None:
    """The verdict row is the whole point of the table, and it names a command by slug. A slug with
    no source is a table that routes the reader nowhere — the failure T03's acceptance review found
    in the other direction (the command pointed at a table that did not yet exist)."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    verdict = [r for r in _lane_table(hub)[1:] if r[0] == "6"]
    assert verdict, "the lane table has no verdict row 6"
    slugs = re.findall(r"/(fabrik-[a-z0-9-]+)", " ".join(verdict[0]))
    assert slugs, f"verdict row names no command: {verdict[0]}"
    missing = [s for s in slugs if not (FABRIK / "commands/_sources" / f"{s}.md").is_file()]
    assert not missing, f"verdict row names commands with no source: {missing}"


def test_the_heavy_surface_list_names_a_governance_sync_path() -> None:
    """§ Completion Contract 1a routes heavy surfaces to the full /fabrik-review. Measured at
    a929b33f8 (spec § The decision rule): 52 of the 97 sync-path commits in the hub's last 300 touch
    ONLY sync paths that 1a's list did not name, so they read as light work and landed one lane
    lighter than a public contract for ~46 repos deserves."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    para = [ln for ln in hub.split("\n") if ln.lstrip().startswith("1a. **SELF-REVIEW")]
    assert len(para) == 1, f"§ 1a's opening line moved or split ({len(para)} matches)"
    assert "a governance-sync path" in para[0], "§ 1a's heavy-surface list omits a governance-sync path"
    # The UNIVERSAL marker in the same paragraph is load-bearing and must not be reworded.
    assert "EVERY code-changing chunk of work gets a review-family pass" in para[0]


def test_the_handle_now_clause_points_at_the_lane_table_instead_of_restating_a_test() -> None:
    """One test, one home (operator ruling U19). The clause keeps its audience's outcomes — the
    reply, the pipeline stage, the right-now fix and its mandated /fabrik-review-scoped — and drops
    only the enumeration that was a second, conflicting test."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    assert hub.count(_LANE_POINTER) == 1, f"pointer count {hub.count(_LANE_POINTER)}, want 1"
    assert _OLD_INLINE_TEST not in hub, "the HANDLE-NOW clause still restates its own sizing test"
    # The outcomes the pointer must NOT have taken with it.
    # The clause points at a table with THREE verdicts; before this assertion existed it named
    # only two, so a row-6 request read as a plain right-now fix and the lane was never opened.
    assert "`/fabrik-task`" in hub.split("SIZING is a required step")[1][:900], (
        "the pointer names no /fabrik-task outcome — the table's third verdict is unreachable"
    )
    for kept in (
        "never half-built inline",
        "**every right-now fix ships with `/fabrik-review-scoped`**",
        "the review comes BEFORE the reply",
    ):
        assert kept in hub, f"the pointer dropped an outcome the clause must keep: {kept}"


def test_the_lane_tables_verdicts_match_the_size_gates_own_routing() -> None:
    """The class four executed mutants walked straight through: rows 1-5's Test and → columns were
    never read by any grader, so flipping row 6's verdict to `/fabrik-spec` (which kills the lane
    outright) passed, and so did widening row 5 from 3 files to 30 while `_TASK_MAX_FILES` stayed 3.

    This binds the table to the gate's own constants, so contract and code cannot drift apart."""
    cr = _load("command_run", "scripts/command_run.py")
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    rows = {r[0]: r for r in _lane_table(hub)[1:]}
    assert len(rows) == 8, sorted(rows)
    assert f"more than {cr._TASK_MAX_FILES} DECLARED files" in rows["5"][1]
    assert "DECLARE the code surface ONLY" in rows["5"][1]
    # round 3 added this caveat and shipped NO grader for it, so inverting it back to "never
    # declare one" passed — re-introducing the exact defect the caveat exists to close.
    assert "is neither excluded nor free" in rows["5"][1]
    assert "the close scores it undeclared" in rows["5"][1]
    # The basis is `--file`, and the COUNT is of DISTINCT normalised paths — the gate dedupes
    # (`src/a.py`, `./src/a.py` and the absolute spelling are one file), so "the `--file` count"
    # read as the occurrence count and was refuted by execution: four occurrences of two paths
    # start at rc 0 (docs review, 2026-09-19). Both halves pinned; the first cut pinned only the
    # flag name, so the wrong quantity survived.
    assert "DISTINCT `--file` paths" in rows["5"][1], "row 5's executable basis is --file, not --declare"
    assert "normalised repo-root-relative" in rows["5"][1], "row 5 must say WHICH count: distinct, normalised"
    assert "excluded at CLOSE, not at start" in rows["5"][1], (
        "row 5 must say WHEN the exclusion applies — it is close-only, and the first cut of\n"
        "this row claimed the --file count itself was already the code surface"
    )
    assert "`/fabrik-task`" in rows["6"][2] and "/fabrik-spec" not in rows["6"][2]
    for n in ("3", "4", "5"):
        assert "spec chain" in rows[n][2], n
    assert "the lane, unless another row fires" in rows["2"][2]  # D-315: row 2 no longer refuses
    for n in ("1", "1b"):
        assert "**not this lane:**" in rows[n][2] and "spec chain" not in rows[n][2], n
        # the FULL review, never the scoped one: these two rows govern a public contract for ~46
        # repos, and downgrading the verdict passed every guard until this line existed.
        assert "the full `/fabrik-review`" in rows[n][2], n
    assert "right-now" in rows["4b"][2] and "spec chain" not in rows["4b"][2]
    # `command_run.py` provably REFUSES the lane for decision=no; the cell said so and nothing
    # stopped it saying the opposite.
    assert "`start` refuses the lane for it" in rows["4b"][2]
    # ⚠️ the VALUE, not just the key: a bare `f"`{key}="` prefix let `mechanism=yes` become
    # `mechanism=no` — teaching the OPPOSITE declaration — in five rows at once.
    for n, kv in (("1b", "heavy=yes"), ("2", "mechanism=yes"), ("3", "oneway=yes"),
                  ("4", "tradeoffs=yes"), ("4b", "decision=no")):
        assert f"`{kv}`" in rows[n][1], (n, kv)
    # the question each row ASKS, not only its label — two rows' prose were swapped wholesale and
    # every grader stayed green, leaving a table that contradicted its own annotations.
    for n, noun in (("1", "governance-sync"), ("1b", "heavy surface"), ("2", "NEW MECHANISM"),
                    ("3", "ONE-WAY"), ("4", "TRADE-OFF"), ("4b", "pure fix")):
        assert noun in rows[n][1], (n, noun)
    assert ".pre-commit-config.yaml" in rows["1"][1]
    for n, phrase in (("1b", "operator-named work"), ("1b", "D-137"),
                      ("3", "expensive to unwind")):
        assert phrase in rows[n][1], (n, phrase)
    assert "PUBLIC CONTRACT" in rows["1"][1], "row 1's QUESTION, not just its parenthetical"
    # the six design fields, which `commands/_sources/fabrik-task.md` also names: a silent
    # divergence here breaks a cross-file contract with nothing to catch it.
    for field in ("PROBLEM", "APPROACH", "DECISION", "MIRROR", "OUT", "TERMINAL"):
        assert field in rows["6"][2], field
    assert "right-now +" in rows["1"][2], "row 1's verdict names a LANE, not just a review"
    assert "the § Binding block lives there" in rows["3"][2]
    # D-298's re-cut, pinned on phrases that exist ONLY in the new wording: "no trade-off" is a
    # prefix of "no trade-off to settle first" and "TRADE-OFF" matches "TRADE-OFFS", so the pins
    # above let a revert to the wording V1 disproved pass 23/23 — executed by the whole-plan seat.
    assert "no trade-off to settle first" in rows["6"][1]
    assert "settled BEFORE building" in rows["4"][1]
    assert "is this lane's ordinary case, not a trigger" in rows["4"][1]
    for conj in ("one reversible decision", f"≤{cr._TASK_MAX_FILES} files", "no sync path",
                 "no heavy surface", "any mechanism reversible", "no trade-off"):
        assert conj in rows["6"][1], conj
    # DERIVED from the table, never a second hand-kept copy of the same five strings: the old
    # closing line compared the constant against a literal it also wrote down, so it could only
    # fail when someone edited the constant — never when the table drifted from it.
    taught = {k for r in rows.values() for k in re.findall(r"`([a-z]+)=[a-z]+`", r[1])}
    assert set(cr._TASK_DECLARE_KEYS) == taught, (set(cr._TASK_DECLARE_KEYS), taught)


def test_the_lane_table_states_the_precedence_the_gate_actually_evaluates() -> None:
    """The rows are PUBLISHED blast-radius-first, but `_task_size_gate` evaluates the file count and
    mechanism/oneway/tradeoffs BEFORE sync and heavy. Read as "first row that fires wins", the
    table sends a >3-file sync-path change to right-now + the full review while the gate refuses it
    to `/fabrik-spec` — the contract and its own gate disagreeing on the hub's most consequential
    surface class. The spec carries the reconciling sentence; the first cut of this table dropped
    it, and three mis-routes were executed against the live parser before it came back."""
    cr = _load("command_run", "scripts/command_run.py")
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    step0 = _step0_body(hub)
    assert hasattr(cr, "_task_size_gate"), "the cited symbol must exist — `_task_size` never did"
    assert "_task_size_gate" in step0, "the precedence claim must cite the function implementing it"
    # The ORDER, read out of the gate itself. `lane = (...)` fires in `if/elif` order, so the
    # sequence of its labels IS the precedence, and a reordering of the gate reds this test.
    src = inspect.getsource(cr._task_size_gate)
    labels = [m.split()[0] for m in re.findall(r'lane = \(f?"([^"]+)"', src)]
    # `mechanism` is absent by ruling (D-315): declared and recorded, never a refusal arm.
    assert labels == ["files", "oneway", "tradeoffs", "sync", "heavy", "decision=no"], labels
    row_of = {"files": "5", "oneway": "3", "tradeoffs": "4",
              "sync": "1", "heavy": "1b", "decision=no": "4b"}
    from_gate = [{row_of[x] for x in labels[:3]}, {row_of[x] for x in labels[3:5]},
                 {row_of[x] for x in labels[5:]}]
    # ⚠️ DERIVED FROM THE TABLE, not from `labels` again: the first cut computed both sides from
    # the same list, so once the labels assertion passed this one could not fail — a second
    # binding that bound nothing. Now the table's own verdict cells are the other side.
    rows = {r[0]: r for r in _lane_table(hub)[1:]}
    from_table = [
        {n for n, r in rows.items() if "spec chain" in r[2]},
        {n for n, r in rows.items() if "**not this lane:**" in r[2]},
        {n for n, r in rows.items() if "/fabrik-review-scoped`" in r[2] and "not this lane" not in r[2]},
    ]
    assert from_gate == from_table, (from_gate, from_table)
    assert "Rows 3, 4 and 5 take PRECEDENCE over rows 1 and 1b" in step0
    assert "which in turn take precedence over row 4b" in step0
    # the tier-1 caveat: the gate checks the file count FIRST, so a refusal naming `files > 3`
    # can still be hiding a row-3/4 trigger. Deleting this clause passed every other guard.
    assert "except INSIDE the spec-chain tier, where the gate reports the file count first" in step0
    assert "any of 3, 4 or 5 is spec-chain work" in step0, (
        "the precedence sentence must state its VERDICT, not only which rows outrank which"
    )
    # the table's own self-correction mechanism, previously guarded by nothing at all
    assert "**Tripwire:**" in step0 and "re-apply tests 1, 1b, 2-5 by hand" in step0
    # the tripwire's FIRING CONDITION and its instruction, not just its heading: inverting
    # "UPGRADE" to "DOWNGRADE" told an agent that a newly-tripping test means narrow further.
    assert "if the first draft cites a script's internals" in step0
    assert "a test that now trips is an UPGRADE, or the draft over-scoped" in step0
    # the no-code clause's VERDICT — it was guarded by five words, and replacing the rest with the
    # opposite verdict ("this lane applies — declare the docs") passed every grader.
    assert "No code surface at all" in step0
    assert "not this lane — declare nothing and `start` refuses" in step0
    # every run needs all five declare keys; "any one of them" passed and costs a round trip.
    # the qualifier was pinned; the claim it qualifies was not, so "a KEY `start` requires"
    # could become "accepts optionally" and leave the sentence self-contradictory.
    assert "names a `--declare` KEY `start` requires — all five, every run" in step0
    assert "`Profile: small` then lightens execution" in step0


def test_the_lane_table_renders_as_a_table_for_every_gfm_reader() -> None:
    """GFM validity, decided by an actual renderer instead of a hand-rolled approximation.

    Three rounds of approximating GFM in `_step0_tables` shipped defects in BOTH directions. False
    negatives: an 8-space indent, a tab indent, a delimiter row one cell short, and the whole table
    wrapped in a fence each render as plain text — the lane table vanishing for every rendered
    reader — while all 17 tests stayed green. False positives: a GFM-legal delimiter row omitting
    either outer pipe reddened four tests on markdown that renders perfectly.

    This asserts the thing that actually matters — the verdict row reaches a table CELL — against
    the renderer, which by construction cannot disagree with GFM about what GFM does."""
    markdown_it = pytest.importorskip("markdown_it", reason="renderer needed to grade GFM validity")
    html = markdown_it.MarkdownIt("gfm-like").enable("table").render(
        _step0_body((FABRIK / "CLAUDE.md").read_text(encoding="utf-8"))
    )
    assert re.search(r"<td>\s*one reversible decision", html), (
        "the lane table's verdict row did not render inside a table cell — the table is "
        "invisible to every rendered reader (check the delimiter row's width, the indentation, "
        "and whether anything fenced it)"
    )


# ── T04b: the lane table MIRRORED into the fleet template ──────────────────────────────────────
# The hub's copy reaches three sessions; the template's reaches ~46 repos on the next governance
# sync, and the failure mode is silent — the hub agent who wrote the table reads it every session
# and never notices the fleet does not have it. Nothing binds the two but a grader like this one.
_TEMPLATE_OUTCOME_II_OLD = "a new mechanism, schema, auth, >5 files"


# Rows that MUST differ between the two contracts, and what the project copy must say. A
# byte-identical mirror was the ticket's premise and the review refuted it by measurement: 38 of 38
# project repos carry a stale, narrower `governance-sync` regex (all 38 omit `^templates/governance/`),
# and `libs/subagents/` was retired from the sync (hub D-196) and is gitignored in 35 of 38.
_TEMPLATE_ROW_DIVERGENCES = {
    "1": "/opt/fabrik/.pre-commit-config.yaml",
    "1b": "copied from fabrik-lib rather than imported",
}


def test_the_lane_table_is_mirrored_into_the_fleet_template_row_for_row() -> None:
    """T04b Behavior Contract: the template's lane table equals the hub's EXCEPT where a project
    repo needs a different answer — and those cells must actually differ, not merely be allowed to.

    Both halves are load-bearing. Unexempted drift is the silent-divergence failure this file
    exists to prevent; an exempted row that stops diverging means the template has quietly
    re-acquired a hub-only path, which is how row 1 shipped a relative `.pre-commit-config.yaml`
    that resolves to a stale regex in every one of the 38 project repos that has one."""
    hub = _lane_table((FABRIK / "CLAUDE.md").read_text(encoding="utf-8"))
    tpl = _lane_table((FABRIK / TEMPLATE_REL).read_text(encoding="utf-8"), _STEP0_END_TPL)
    assert len(tpl) == len(hub), (len(tpl), len(hub))
    for h, t in zip(hub, tpl, strict=True):
        if h[0] in _TEMPLATE_ROW_DIVERGENCES:
            assert h != t, f"row {h[0]} must differ for a project repo and no longer does"
            assert _TEMPLATE_ROW_DIVERGENCES[h[0]] in " ".join(t), (h[0], t)
        else:
            assert h == t, f"row {h[0]} diverges between the hub and the fleet template: {h} vs {t}"


def test_the_templates_mirrored_prose_matches_the_hubs() -> None:
    """The lane table ships with three PROSE paragraphs — the precedence sentence, the no-code
    clause and the tripwire — and the row-comparison above reads none of them. Executed: inverting
    the template's no-code verdict to "take the `/fabrik-task` lane anyway", gutting the tripwire,
    and deleting both paragraphs outright each passed the whole suite."""
    hub_s = _step0_body((FABRIK / "CLAUDE.md").read_text(encoding="utf-8"))
    tpl_s = _step0_body((FABRIK / TEMPLATE_REL).read_text(encoding="utf-8"), _STEP0_END_TPL)
    for lead in ("**No code surface at all**", "**Tripwire:**"):
        assert lead in tpl_s, f"the template lost a mirrored paragraph: {lead}"
        h = hub_s[hub_s.index(lead):].split("\n", 1)[0]
        t = tpl_s[tpl_s.index(lead):].split("\n", 1)[0]
        # the hub names `docs/CAPABILITIES.md`, which exists in 1 of 45 repos; the template says
        # "docs or ledgers only" instead. That is the only sanctioned difference in these two.
        if lead == "**No code surface at all**":
            assert "(docs or ledgers only)" in t
            h, t = h.replace(" or `docs/CAPABILITIES.md`", "").replace("(docs, ledgers", "(docs"), t
            assert h.replace("(docs only)", "(docs or ledgers only)") == t, (h, t)
        else:
            assert h == t, f"mirrored paragraph drifted: {lead}"
    # the precedence claim, which the hub binds and the template did not
    assert "Rows 3, 4 and 5 take PRECEDENCE over rows 1 and 1b" in tpl_s
    assert "any of 3, 4 or 5 is spec-chain work" in tpl_s
    # and the ordering the SPEC mandates for the project copy: outcome (i) outranks the table
    assert "ahead of every test below" in tpl_s
    assert "Editing the synced copy is a HARD STOP" in tpl_s


def test_the_template_renders_its_lane_table_for_every_gfm_reader() -> None:
    """The mirror is worthless if it renders as a paragraph in ~46 repos."""
    markdown_it = pytest.importorskip("markdown_it", reason="renderer needed to grade GFM validity")
    html = markdown_it.MarkdownIt("gfm-like").enable("table").render(
        _step0_body((FABRIK / TEMPLATE_REL).read_text(encoding="utf-8"), _STEP0_END_TPL)
    )
    assert re.search(r"<td>\s*one reversible decision", html), (
        "the template's lane table did not render inside a table cell — it would be invisible "
        "to every reader in ~46 repos"
    )


def test_the_templates_heavy_surface_list_names_a_governance_sync_path() -> None:
    """§ 1a's trigger, mirrored. In a PROJECT repo the synced set is never hand-edited, so this
    refuses almost nothing there — it is carried for parity, and because a project that vendors a
    synced surface locally is exactly the case it must catch."""
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    para = [ln for ln in tpl.split("\n") if ln.lstrip().startswith("1a. **SELF-REVIEW")]
    assert len(para) == 1, f"§ 1a's opening line moved or split ({len(para)} matches)"
    assert "gate/hook/enforcement, a governance-sync path, auth/schema" in para[0], (
        "the trigger must sit INSIDE the heavy-surface list — a bare substring check let it be "
        "removed from the list and re-added as a negating sentence on the same line"
    )
    assert "EVERY code-changing chunk of work gets a review-family pass" in para[0]


def test_the_templates_outcome_ii_points_at_the_lane_table_and_keeps_all_three() -> None:
    """Operator ruling U19, mirrored — one test, one home. The project copy carries D-098's own
    third outcome (a synced-surface defect files UPSTREAM) which the hub has no equivalent of, so
    only outcome (ii) collapses; (i) and (iii) survive untouched, and the lane the table's verdict
    row names must be reachable from the clause that points at it."""
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    assert _LANE_POINTER in tpl, "outcome (ii) does not point at the lane table"
    assert _TEMPLATE_OUTCOME_II_OLD not in tpl, "outcome (ii) still restates its own sizing test"
    clause = tpl.split("it has THREE outcomes, not two:", 1)[1].split("Mail is worked by", 1)[0]
    assert "`/fabrik-task`" in clause, (
        "the table's row-6 verdict is unreachable from the mail clause — the first cut of this "
        "assertion read the WHOLE file, so the lane table's own row 6 satisfied it and a mutation "
        "that severed the clause from `/fabrik-task` entirely passed green"
    )
    for kept in (
        "it is NOT yours to plan or patch, file it upstream",
        "never half-built inline",
        "**every right-now fix ships with `/fabrik-review-scoped`**",
        "the review comes BEFORE",
    ):
        assert kept in tpl, f"outcome (i), (ii) or (iii) lost an obligation: {kept}"


# The GATE row cites `final_gate.py` by LINE (D-284 — the paraphrase drifted once), and the pins above
# only prove the two contracts say the SAME thing. Nothing proved the lines still hold what the
# sentence names, so a 16-line insertion in `final_gate.py` (mail 01M37YR2KDNCE8V5YTRDHRB7D6) would
# have left every cite pointing at the wrong code, green. Each cite -> the text its FIRST line must
# carry. ⚠️ COBRA: the cheapest way to green this after moving code is to edit the expected text
# here instead of the cite in both contracts; the text below names the construct, never a line, so
# such an edit is visible in review as a change of MEANING.
_GATE_CITES = {
    ":70": "PROJECT_ROOT = Path.cwd()",
    ":335-348": "WARN_ONLY_CHECKS: set[str] = {",
    ":1009": "if tier == 3:",
    ":1026": "return results",
    ":1125": "return results",
    "final_gate.py:1280-1290": "if (",
    ":1299": "elif code == 5:",
    ":1339": "if code != 0 and _PYTEST_EARLY_STOP in out:",
    ":2896-2912": "missing = _toolchain_missing(PYTHON)",
    ":2914-2920": "# Determine tier",
}


# The hub contract alone says where ruff must RESOLVE (the template's GATE row omits that sentence).
_HUB_ONLY_GATE_CITES = {":81": "RUFF = str(VENV_RUFF)"}


def test_the_gate_rows_line_citations_land_on_what_they_name() -> None:
    gate = (FABRIK / "scripts" / "final_gate.py").read_text(encoding="utf-8").splitlines()
    for contract in (FABRIK / "CLAUDE.md", FABRIK / "templates" / "governance" / "CLAUDE.md"):
        text = contract.read_text(encoding="utf-8")
        for cite, construct in _GATE_CITES.items():
            assert cite in text, (
                f"{contract.name}: the cite {cite} is gone — re-derive it, both contracts"
            )
            first = int(cite.rsplit(":", 1)[1].split("-")[0])
            assert gate[first - 1].strip().startswith(construct), (
                f"final_gate.py:{first} no longer holds {construct!r} — move the cite in BOTH contracts"
            )
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    for cite, construct in _HUB_ONLY_GATE_CITES.items():
        assert cite in hub, f"CLAUDE.md: the cite {cite} is gone — re-derive it"
        assert gate[int(cite[1:]) - 1].startswith(construct), (
            f"final_gate.py{cite} no longer holds {construct!r}"
        )

# ── T02a: the DECISION block lives in § FINAL OUTPUT, plus # Compact instructions ────────────
# docs/development/plans/2026-09-23-plan-1-stop-and-compaction/T02a-hub-claude-md.md, implementing
# docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md § C2 (the DECISION
# block) and § C4 (the summarizer's instructions). Hub-only; T02b mirrors it into
# templates/governance/CLAUDE.md, serialized after this ticket per the plan's Merge Order.
#
# Round 1 review (orchestrator-adjudicated) found the first cut's graders read the SECTION as a
# whole, so a defect INSIDE one fenced block (a dropped field, a mislabelled example, required
# text hidden in a fence) stayed invisible as long as the phrase existed SOMEWHERE else in the
# section. The helpers below scope each check to the fenced block or paragraph that actually owns
# the claim.

_DECISION_FORMAT_LINES = (
    "DECISION NEEDED (ground: gate|underivable|owned)",
    "- Question:",
    "- Why it is yours:",
    "- Options:",
    "- Recommendation:",
)


def _final_output_section(text: str) -> str:
    start = "## ⚠️ FINAL OUTPUT"
    assert text.count(start) == 1, "§ FINAL OUTPUT heading drifted"
    body = text.split(start, 1)[1]
    end = "\n## "
    return body.split(end, 1)[0] if end in body else body


def _fenced_blocks(text: str) -> list[str]:
    """Every fenced code block's CONTENTS (between a `` ``` `` pair), in document order."""
    return re.findall(r"```\n(.*?)```", text, re.DOTALL)


def _decision_format_block(section: str) -> str:
    """The canonical DECISION block FORMAT — the fenced block headed by the bare
    `ground: gate|underivable|owned` heading, never one of the two worked examples below it."""
    for block in _fenced_blocks(section):
        if block.startswith("DECISION NEEDED (ground: gate|underivable|owned)"):
            return block
    raise AssertionError("no fenced block headed by the canonical DECISION NEEDED format line")


def _decision_example(section: str, ground: str) -> str:
    """One worked example's fenced block, addressed by its own `ground:` token (`gate`/`owned`)."""
    for block in _fenced_blocks(section):
        if block.startswith(f"DECISION NEEDED (ground: {ground})"):
            return block
    raise AssertionError(f"no fenced DECISION example for ground={ground!r}")


def test_final_output_carries_the_decision_block_format() -> None:
    """T02a Behavior Contract: the DECISION block's shape lives in § FINAL OUTPUT (spec § C2),
    scoped to the CANONICAL format block (O3) — both worked examples below it also carry
    `- Question:` etc., so an unscoped check stays green even when a field is deleted from the
    format block alone.

    Mutant (O3): delete `- Recommendation: <A or B, and the one-line reason>` from the format
    block only, leaving both examples' own `- Recommendation:` lines untouched — RED."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    section = _final_output_section(hub)
    block = _decision_format_block(section)
    for line in _DECISION_FORMAT_LINES:
        assert line in block, f"the DECISION format block is missing: {line!r}"


def test_final_output_carries_exactly_two_decision_examples() -> None:
    """The section carries one legitimate and one refused DECISION example (spec § C2, graft G-c)."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    section = _final_output_section(hub)
    assert section.count("DECISION NEEDED (ground:") == 3, (
        "expected the format block plus exactly two examples beside it"
    )
    assert "ground: gate)" in section, "no legitimate (ground: gate) example"
    assert "ground: owned)" in section, "no refused (ground: owned) example"
    assert "Legitimate" in section, "the legitimate example is not labelled"
    assert "Refused" in section and "REFUSED" in section, "the refused example is not labelled"


def test_final_output_examples_bind_the_right_label_to_the_right_ground() -> None:
    """O8: the Legitimate label must sit with the `ground: gate` example, and Refused with
    `ground: owned` — not merely present somewhere in the section (which a swap would still
    satisfy).

    Mutant (O8): swap the two `ground:` tokens between the two example blocks so the Legitimate
    example reads `(ground: owned)` and the Refused one reads `(ground: gate)` — RED."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    section = _final_output_section(hub)
    legit_idx = section.index("Legitimate")
    refused_idx = section.index("Refused")
    assert legit_idx < refused_idx, "the legitimate example must precede the refused one"
    legit_span = section[legit_idx:refused_idx]
    refused_span = section[refused_idx:]
    assert "DECISION NEEDED (ground: gate)" in legit_span, (
        "the Legitimate label is not bound to the ground: gate example"
    )
    assert "DECISION NEEDED (ground: owned)" in refused_span, (
        "the Refused label is not bound to the ground: owned example"
    )


def test_final_output_templates_point_at_the_decision_block() -> None:
    """S1/O5: the 7-line template's `NEXT:` field and the STATE footer's `NEXT:` field both point
    at the DECISION block, instead of leaving a bare `operator decision` unexplained.

    Mutant (S1/O5-a): delete ' — see DECISION NEEDED above' from the 7-line template's NEXT
    line — RED. Mutant (S1/O5-b): delete it from the STATE footer's NEXT line — RED."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    section = _final_output_section(hub)
    assert "operator decision: <what> — see DECISION NEEDED above" in section, (
        "the 7-line template's NEXT field does not point at the DECISION block"
    )
    assert "the operator decision awaited — see DECISION NEEDED above" in section, (
        "the STATE footer's NEXT field does not point at the DECISION block"
    )


def test_operator_decision_bar_bullet_keeps_its_anchor_and_names_the_block() -> None:
    """The § UNIVERSAL governance markers bullet (CLAUDE.md:385) keeps its anchor verbatim
    (anchors are case-exact and must never be reworded) and now names the DECISION block."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    bullets = [ln for ln in hub.split("\n") if ln.lstrip().startswith("- `operator-decision-bar`")]
    assert len(bullets) == 1, f"operator-decision-bar bullet moved or duplicated ({len(bullets)})"
    bullet = bullets[0]
    assert "`NEXT: operator decision` HAS A BAR" in bullet, "the anchor was reworded"
    assert "DECISION NEEDED" in bullet, "the bullet does not name the DECISION block"


_BAR_PARAGRAPH_MARKER = "**⚠️ `NEXT: operator decision` HAS A BAR"


def _has_a_bar_paragraph(hub: str) -> str:
    """The HAS A BAR paragraph, bounded at the 'Legitimate:' label that follows it."""
    assert hub.count(_BAR_PARAGRAPH_MARKER) == 1, "the HAS A BAR paragraph moved or duplicated"
    after = hub.split(_BAR_PARAGRAPH_MARKER, 1)[1]
    end = "\n\nLegitimate:"
    assert end in after, "the paragraph no longer precedes the Legitimate example"
    return _BAR_PARAGRAPH_MARKER + after.split(end, 1)[0]


_CLOSED_GATE_CLASS_LIST = (
    "deploy · destructive · irreversible · spend (real money) · cross-repo · publish · "
    "credentials · design approval · plan approval · Gate 1 · Gate 2 · production data"
)


def test_the_bar_paragraph_keeps_every_restored_and_new_rule() -> None:
    """H1/O2 restore two rules the DECISION-block rewrite silently dropped from the pre-T02a
    paragraph (`git show 5c31f796c:CLAUDE.md`) — the positive instruction after the menu ban
    ("derive the verdict, state it, proceed"), and the own-reliability/fatigue/context-budget
    citation being a `BLOCKED:`. O1 (write the block unfenced) and O6 (the closed gate-class list)
    are rules this round adds. Round 2 (O3) fixed the closed list's own worked example — the §
    EXIT ad-hoc-branch disposition is now named by an actual list token (`destructive`) instead of
    being cited as its own, undeclared ground. Round 2 (O2) also widened this grader to the
    paragraph's headline rules: the `(a)/(b)` menu ban, "DISPATCHED, not offered", `scope:`
    refused mid-run, and `searched:` for `underivable`. Each is asserted INSIDE the paragraph
    itself, and the universal bullet keeps its own closing phrase.

    Mutants (each deleted alone from the paragraph, each must go RED):
    - H1: delete "derive the verdict, state it, proceed"
    - O2: delete "is a `BLOCKED:` if it is anything at all"
    - O1: delete "written unfenced"
    - O6: delete "Gate 1 · Gate 2 · production data" from the closed class list
    - O3 (round 2): delete "is named `destructive`, since discarding a branch/worktree is the
      destructive act" — the ad-hoc-branch disposition would again cite itself as a ground with no
      list token, which the hook refuses
    - O2 (round 2), one mutant per rule:
      - delete "an `(a)/(b)` options menu is never legitimate"
      - delete "**Everything else is DISPATCHED, not offered**"
      - delete "refused while a command run record is `running`"
      - delete "with `searched:` naming what came back silent"
    """
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    para = _has_a_bar_paragraph(hub)
    assert "`gate`" in para and "`underivable`" in para and "`owned`" in para
    assert "`asked:`" in para and "`scope:`" in para
    assert "derive the verdict, state it, proceed" in para, (
        "H1: the positive after-menu-ban rule is missing"
    )
    assert "is a `BLOCKED:` if it is anything at all" in para, (
        "O2: the own-reliability -> BLOCKED: rule is missing"
    )
    assert "written unfenced" in para, "O1: the unfenced-writing rule is missing"
    assert _CLOSED_GATE_CLASS_LIST in para, "O6: the closed gate-class list is missing or drifted"
    assert (
        "is named `destructive`, since discarding a branch/worktree is the destructive act"
        in para
    ), "O3 (round 2): the ad-hoc-branch disposition names no list token"
    assert "an `(a)/(b)` options menu is never legitimate" in para, (
        "O2 (round 2): the (a)/(b) options-menu ban is missing"
    )
    assert "**Everything else is DISPATCHED, not offered**" in para, (
        "O2 (round 2): the DISPATCHED-not-offered rule is missing"
    )
    assert "refused while a command run record is `running`" in para, (
        "O2 (round 2): the scope:-refused-while-live rule is missing"
    )
    assert "with `searched:` naming what came back silent" in para, (
        "O2 (round 2): the underivable ground's searched: requirement is missing"
    )

    bullets = [ln for ln in hub.split("\n") if ln.lstrip().startswith("- `operator-decision-bar`")]
    assert len(bullets) == 1
    assert "never a menu, never your own uncertainty" in bullets[0], (
        "the universal bullet lost its closing phrase"
    )


def test_the_decision_block_is_stated_as_unfenced_beside_the_format() -> None:
    """O1: nothing in the pre-round-1 text said the REAL block must be written outside a code
    fence, so a well-formed but fenced block silently read as compliant. The rule now sits right
    beside the format block it governs.

    Mutant: delete 'a fenced example, like the two below, never exempts a turn' — RED."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    para = _has_a_bar_paragraph(hub)
    assert "written unfenced" in para
    assert "a fenced example, like the two below, never exempts a turn" in para


_COMPACT_INSTRUCTIONS_LINES = (
    "the live command and its terminal condition",
    "every file path and plan/spec path being worked",
    "every operator ruling of the session, in the operator's words",
    "the pending DECISION block",
    "the last `NEXT:`",
)


def _next_heading_bound(text: str) -> str:
    """Bounded at the NEXT heading of any level, never the whole rest of the file."""
    m = re.search(r"\n#{1,6} ", text)
    return text[: m.start()] if m else text


def _unfenced(text: str) -> str:
    """Strip fenced code blocks out of consideration (O7) — required instructional text that
    exists only inside a fence is not read by the summarizer as an instruction, mirroring the
    DECISION block's own unfenced rule."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def test_compact_instructions_heading_exists_with_its_five_lines() -> None:
    """T02a Behavior Contract: a top-level `# Compact instructions` heading (spec § C4, E5) — the
    summarizer reads this exact heading from the root CLAUDE.md, so it is an H1 like the file's own
    title, not one of its usual `##` sections. Bounded to the NEXT heading and fenced text
    stripped (O7), and the HEADING ITSELF is now checked fence-aware too (round 2, O1): a heading
    that exists only inside a code fence is a worked example, never a real top-level heading the
    summarizer would honour.

    Mutant (O7): wrap '- the pending DECISION block, if any;' in a ``` fence inside the section
    (leaving every other line untouched) — RED. Mutant (O1, round 2): wrap the
    '# Compact instructions' heading LINE ITSELF in a ``` fence — RED (the heading no longer counts
    once fences are stripped first)."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    unfenced_hub = _unfenced(hub)
    assert unfenced_hub.count("\n# Compact instructions\n") == 1, (
        "the heading is missing, duplicated, fenced, or not written as a top-level H1"
    )
    raw_body = unfenced_hub.split("# Compact instructions", 1)[1]
    body = _next_heading_bound(raw_body)
    for line in _COMPACT_INSTRUCTIONS_LINES:
        assert line in body, f"# Compact instructions is missing a required line: {line!r}"
    # whitespace-normalised: the file hard-wraps prose at ~100 columns, and a wrap boundary
    # landing inside this sentence must not read as the sentence being missing (memory note
    # extending-a-sentence-unanchors-its-pinned-span).
    normalised = re.sub(r"\s+", " ", body)
    assert "never summarise a pending operator question as settled" in normalised.lower()
    assert "Context is never a reason to stop, and a fresh session is never the remedy" in normalised
    assert "D-374" in body, "the sentence must cite D-374"


# ── T02b: the DECISION block MIRRORED into templates/governance/CLAUDE.md ──────────────────────
# docs/development/plans/2026-09-23-plan-1-stop-and-compaction/T02b-template-claude-md.md. The
# template carries § FINAL OUTPUT TWICE (:629, :672 pre-edit) — the duplication itself is routed to
# docs/STRATEGIC_BACKLOG.md by T06, never fixed here — so every grader below checks BOTH copies.
# Nothing binds the template to the hub's T02a text but a grader like this one: the hub agent who
# wrote the DECISION block reads it every session and would never notice the ~46 synced repos
# still taught the old, unguarded `operator decision:` exit.


def _final_output_sections(text: str) -> list[str]:
    """Every § FINAL OUTPUT section in document order.

    O5: the template carries the block EXACTLY twice — a looser `>= 1` bound would silently accept
    a renamed or removed second heading, and every per-copy grader below would then check copy 1
    alone, twice, while reporting "template copy 2" for what is really copy 1's text again."""
    start = "## ⚠️ FINAL OUTPUT"
    end = "\n## "
    parts = text.split(start)[1:]
    assert len(parts) == 2, f"expected exactly 2 § FINAL OUTPUT copies, found {len(parts)}"
    return [p.split(end, 1)[0] if end in p else p for p in parts]


def _has_a_bar_paragraph_in(section: str) -> str:
    """The HAS A BAR paragraph scoped to ONE § FINAL OUTPUT section, bounded at 'Legitimate:'."""
    assert section.count(_BAR_PARAGRAPH_MARKER) == 1, (
        "the HAS A BAR paragraph is missing or duplicated in this § FINAL OUTPUT copy"
    )
    after = section.split(_BAR_PARAGRAPH_MARKER, 1)[1]
    end = "\n\nLegitimate:"
    assert end in after, "the paragraph no longer precedes the Legitimate example"
    return _BAR_PARAGRAPH_MARKER + after.split(end, 1)[0]


_REFUSED_VERDICT_SENTENCE_END = "the `(a)/(b)` menu the grounds above forbid."


def _bar_through_refused_verdict_in(section: str) -> str:
    """O4: the WHOLE load-bearing span, scoped to ONE § FINAL OUTPUT section — from the HAS A BAR
    paragraph's own opening sentence through the REFUSED verdict sentence at the very end. This
    covers the DECISION-format-block prose, BOTH worked examples with their 'Legitimate'/'Refused'
    labels, and the closing verdict, as ONE contiguous byte span.

    The narrower per-piece checks (the isolated fenced examples via `_decision_example`, the bar
    paragraph alone via `_has_a_bar_paragraph_in`) never read the text BETWEEN the fenced blocks,
    so a rewritten or inverted REFUSED rationale, or a relabelled example, stayed green against
    them (O4's own finding). This helper closes that gap without touching either narrower one."""
    assert section.count(_BAR_PARAGRAPH_MARKER) == 1, (
        "the HAS A BAR paragraph is missing or duplicated in this § FINAL OUTPUT copy"
    )
    start = section.index(_BAR_PARAGRAPH_MARKER)
    assert section.count(_REFUSED_VERDICT_SENTENCE_END) == 1, (
        "the REFUSED verdict sentence is missing or duplicated in this § FINAL OUTPUT copy"
    )
    end = section.index(_REFUSED_VERDICT_SENTENCE_END) + len(_REFUSED_VERDICT_SENTENCE_END)
    return section[start:end]


# O3/S2: the ONLY sanctioned divergence inside the bar-paragraph/examples span and the Compact
# instructions section — the template's own `hub D-NNN` convention (:25, :69, :226, :374, :617)
# prefixes a HUB decision id so a project's own SAME-NUMBERED id in its own docs/DECISIONS.md is
# never confused with the hub's (measured: 2 of 49 project repos carry a different D-054 locally).
# The hub file needs no such prefix — it IS the hub. A closed, named mapping like
# _TEMPLATE_ROW_DIVERGENCES / _HUB_ONLY_GATE_CITES: nothing else may differ once these are applied.
_BAR_PARAGRAPH_ID_REWRITE = ("kept whole from D-054:", "kept whole from hub D-054:")
_COMPACT_INSTRUCTIONS_ID_REWRITE = ("never the remedy (D-374).", "never the remedy (hub D-374).")


def _rewrite_hub_id(text: str, rewrite: tuple[str, str]) -> str:
    """Apply ONE sanctioned hub->template id rewrite, asserting the hub spelling appears exactly
    once first — a rewrite that silently matches zero (or more than one) span is a rewrite that
    proves nothing, the same failure mode `_TEMPLATE_ROW_DIVERGENCES` guards against."""
    old, new = rewrite
    assert text.count(old) == 1, f"expected exactly one {old!r} in the hub text, found {text.count(old)}"
    return text.replace(old, new)


def test_the_templates_final_output_copies_carry_the_decision_block_format() -> None:
    """T02b Behavior Contract: every § FINAL OUTPUT copy in the template carries the SAME DECISION
    block FORMAT as the hub's, byte-identical (spec § Contract deltas).

    Mutant: delete '- Recommendation: <A or B, and the one-line reason>' from ONE of the two
    template copies' format blocks only — RED for that copy, proving the check is per-copy, not a
    single whole-file substring search that the other copy's surviving text would satisfy."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    hub_block = _decision_format_block(_final_output_section(hub))
    for i, section in enumerate(_final_output_sections(tpl), start=1):
        block = _decision_format_block(section)
        assert block == hub_block, f"template copy {i}'s DECISION format block drifted from the hub"


def test_the_templates_final_output_copies_carry_the_two_decision_examples() -> None:
    """The Legitimate/Refused worked examples, byte-identical to the hub's, in BOTH copies.

    Mutant: swap the `ground:` tokens between the two examples in one copy only — RED for that
    copy."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    hub_section = _final_output_section(hub)
    hub_gate = _decision_example(hub_section, "gate")
    hub_owned = _decision_example(hub_section, "owned")
    for i, section in enumerate(_final_output_sections(tpl), start=1):
        assert section.count("DECISION NEEDED (ground:") == 3, (
            f"template copy {i}: expected the format block plus exactly two examples"
        )
        assert "Legitimate" in section, f"template copy {i}: legitimate example not labelled"
        assert "Refused" in section and "REFUSED" in section, (
            f"template copy {i}: refused example not labelled"
        )
        assert _decision_example(section, "gate") == hub_gate, (
            f"template copy {i}: legitimate example drifted from the hub"
        )
        assert _decision_example(section, "owned") == hub_owned, (
            f"template copy {i}: refused example drifted from the hub"
        )


def test_the_templates_final_output_next_lines_point_at_the_decision_block() -> None:
    """S1/O5 mirrored: the 7-line template's `NEXT:` and the STATE footer's `NEXT:` both point at
    the DECISION block in BOTH template copies.

    Mutant: delete ' — see DECISION NEEDED above' from one copy's 7-line `NEXT:` line — RED for
    that copy."""
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    for i, section in enumerate(_final_output_sections(tpl), start=1):
        assert "operator decision: <what> — see DECISION NEEDED above" in section, (
            f"template copy {i}: the 7-line template's NEXT field does not point at the DECISION "
            "block"
        )
        assert "the operator decision awaited — see DECISION NEEDED above" in section, (
            f"template copy {i}: the STATE footer's NEXT field does not point at the DECISION block"
        )


def test_the_templates_bar_paragraph_matches_the_hub_in_both_copies() -> None:
    """The full HAS A BAR paragraph — every restored and new rule from the hub's T02a round —
    byte-identical in BOTH template copies, up to the ONE sanctioned `hub D-054` id rewrite.

    Mutant: delete 'is a `BLOCKED:` if it is anything at all' from one copy's paragraph only — RED
    for that copy."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    hub_para = _rewrite_hub_id(_has_a_bar_paragraph(hub), _BAR_PARAGRAPH_ID_REWRITE)
    for i, section in enumerate(_final_output_sections(tpl), start=1):
        assert _has_a_bar_paragraph_in(section) == hub_para, (
            f"template copy {i}'s HAS A BAR paragraph drifted from the hub"
        )


def test_the_templates_bar_paragraph_and_examples_match_the_hub_end_to_end() -> None:
    """O4: byte-identity over the WHOLE load-bearing span in each copy — the bar paragraph, both
    worked examples with their 'Legitimate'/'Refused' labels, and the REFUSED verdict sentence —
    not just the isolated fenced blocks the narrower checks above compare. Those narrower checks
    never read the text BETWEEN the fenced blocks, so a rewritten or inverted REFUSED rationale, or
    a swapped 'Legitimate'/'Refused' label pair, stayed green against them.

    Mutant: reword the REFUSED verdict sentence in copy 2 only (leave both fenced examples and
    their `ground:` tokens untouched) — RED for that copy, where every narrower check above stays
    green."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    hub_span = _rewrite_hub_id(
        _bar_through_refused_verdict_in(_final_output_section(hub)), _BAR_PARAGRAPH_ID_REWRITE
    )
    for i, section in enumerate(_final_output_sections(tpl), start=1):
        assert _bar_through_refused_verdict_in(section) == hub_span, (
            f"template copy {i}'s bar-paragraph-through-REFUSED-verdict span drifted from the hub"
        )


def test_the_templates_universal_marker_index_names_the_decision_block() -> None:
    """The template's condensed UNIVERSAL-markers index line (the anchor-only list, a sanctioned
    format divergence from the hub's per-bullet table) keeps the `operator-decision-bar` anchor
    verbatim and now names the DECISION block, mirroring the hub bullet's own T02a addition.

    Mutant: delete '(the `DECISION NEEDED` block)' from the index line — RED."""
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    # Excludes the two HAS A BAR paragraphs (one per § FINAL OUTPUT copy), which also carry the
    # anchor substring but are identified by their own unique lead-in text.
    lines = [
        ln
        for ln in tpl.split("\n")
        if "NEXT: operator decision` HAS A BAR" in ln and "UNGUARDED exit" not in ln
    ]
    assert len(lines) == 1, f"the anchor line moved or duplicated ({len(lines)})"
    line = lines[0]
    assert "`NEXT: operator decision` HAS A BAR" in line, "the anchor was reworded"
    assert "DECISION NEEDED" in line, "the index line does not name the DECISION block"


def test_the_templates_compact_instructions_match_the_hub() -> None:
    """T02b: `# Compact instructions` is a top-level H1 in the template too, identical to the
    hub's up to the ONE sanctioned `hub D-374` id rewrite (O3/S2) — the section names no other
    hub-only path or fact, so nothing else in it is a sanctioned divergence.

    Mutant: wrap '- the pending DECISION block, if any;' in a ``` fence inside the template's
    section — RED (fences are stripped before comparison, so the line reads as missing)."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    tpl = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    unfenced_hub = _unfenced(hub)
    unfenced_tpl = _unfenced(tpl)
    assert unfenced_tpl.count("\n# Compact instructions\n") == 1, (
        "the heading is missing, duplicated, fenced, or not written as a top-level H1"
    )
    hub_body = _rewrite_hub_id(
        _next_heading_bound(unfenced_hub.split("# Compact instructions", 1)[1]),
        _COMPACT_INSTRUCTIONS_ID_REWRITE,
    )
    tpl_body = _next_heading_bound(unfenced_tpl.split("# Compact instructions", 1)[1])
    assert tpl_body == hub_body, "the template's # Compact instructions drifted from the hub's"
