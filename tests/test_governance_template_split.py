# AFTER-EDIT: scripts/fabrik_synced_manifest.py, scripts/sync_enforcement_to_projects.py
"""CLAUDE.md hub/project split — the fleet template is sourced from
templates/governance/CLAUDE.md, never from the hub's own /opt/fabrik/CLAUDE.md
(which is the HUB agents' contract, not a distributed file).

Plan: docs/development/plans/2026-08-08-plan-1-claude-md-hub-split.md (Phase A).
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

FABRIK = Path(__file__).resolve().parents[1]
TEMPLATE_REL = "templates/governance/CLAUDE.md"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, FABRIK / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(FABRIK / "scripts"))
    sys.modules[name] = mod  # dataclass decoration resolves cls.__module__ here
    spec.loader.exec_module(mod)
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
    "in a Tier-2 run (the default tier — only `--lean`/`--systemic` change it, `:2895-2901`)",
    "the rows that can never fail — `WARN_ONLY_CHECKS`, `:327-340` — carrying each one's own text",
    "only a leg that ran to completion is the bare `pytest`",
    "`skipped_checks` (bare NAMES — both rows reduce to `pytest` there, never the reason) AND `advisory`",
    "a `status: \"setup-error\"` envelope (`:2877-2893` — the `REQUIRED_TOOLS` probe, ruff OR pytest missing, before any tier runs) carries none of these keys",
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
    "under 85 — GREEN",
    "85 to under 90",
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
    "**under 85 — GREEN:**",
    "85 to under 90",
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
