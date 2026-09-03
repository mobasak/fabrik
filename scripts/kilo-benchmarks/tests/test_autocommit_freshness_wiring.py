# AFTER-EDIT: ../autocommit_pipeline_outputs.sh | ../guard_selection_freshness.py
"""The SHELL wiring of the freshness guard — untested before (review 2026-09-02, finding 9).

The filter's own tests exercise the python; they say nothing about how bash consumes it, and the
bash side is where the dangerous failure lived: `mapfile -t PATHS < <(cmd || fallback)` hides the
helper's exit code, so a helper exiting 0 with no output wiped PATHS to zero — the stage loop ran
zero times and the `${#STAGED[@]} -ne ${#PATHS[@]}` check compared 0 against 0 and stayed silent.
`test_golden_parity.py:1338` is already named for that failure class and could not catch this
because it only greps for literal strings, so these drive the REAL contract instead.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
GUARD = SCRIPTS / "guard_selection_freshness.py"


def _run(script: str, repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, cwd=str(repo),
    )


def _repo(tmp_path: Path, committed_date: str, worktree_date: str) -> tuple[Path, str]:
    r = tmp_path / "r"
    rel = "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
    (r / "docs/reference/kilo").mkdir(parents=True)
    for cmd in (["init", "-q", "."], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(r), *cmd], check=True)
    (r / rel).write_text(f"Last refresh: {committed_date}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(r), "add", rel], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "base"], check=True)
    (r / rel).write_text(f"Last refresh: {worktree_date}\n", encoding="utf-8")
    return r, rel


# ⚠️ SLICED FROM THE SHIPPED FILE, never transcribed. The previous version was an f-string copy of
# the block, and it graded NOTHING: deleting the entire guard block from
# autocommit_pipeline_outputs.sh left all six of these tests GREEN (proven 2026-09-02, round 2 late
# finder). A test that drives a copy tests the copy. `test_golden_parity.py::_hook_inner_block`
# already solved this for the other block; this is the same fix.
SH = SCRIPTS / "autocommit_pipeline_outputs.sh"
_SENTINEL_OPEN = "# >>> FRESHNESS-GUARD-BLOCK"
_SENTINEL_CLOSE = "# <<< FRESHNESS-GUARD-BLOCK"


def _shipped_guard_block() -> str:
    """The REAL guard block, cut from the shipped script between its sentinels."""
    text = SH.read_text(encoding="utf-8")
    assert _SENTINEL_OPEN in text and _SENTINEL_CLOSE in text, (
        "the sentinels around the guard block are gone from autocommit_pipeline_outputs.sh — "
        "these tests can no longer drive the shipped code, which is the failure they exist to stop"
    )
    # ⚠️ split on LINES, not on the substring: the sentinel line carries a trailing parenthetical,
    # and splitting mid-line left `(sentinels are LOAD-BEARING…` as bare bash — an unclosed paren.
    lines = text.splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith(_SENTINEL_OPEN))
    j = next(n for n, ln in enumerate(lines) if ln.startswith(_SENTINEL_CLOSE))
    # skip the opening sentinel's own comment lines; keep everything executable up to the close
    block = "\n".join(
        ln for ln in lines[i + 1 : j] if not (ln.startswith("#") and "sentinel" in ln.lower())
    )
    assert "guard_selection_freshness.py" in block, (
        "the sliced block no longer invokes the guard — the wiring under test has been removed"
    )
    return block


def _wiring(paths_literal: str, guard_cmd: str | None = None) -> str:
    """Harness preamble + the SHIPPED block + a reporting tail."""
    block = _shipped_guard_block()
    if guard_cmd is not None:  # only for the crash-path test, which must break the helper on purpose
        block = block.replace(
            'python3 "$SELF_DIR/guard_selection_freshness.py"', guard_cmd
        )
    return (
        "set -u\n"
        'FABRIK_ROOT="$PWD"\n'
        f'SELF_DIR="{SCRIPTS}"\n'
        f"PATHS=({paths_literal})\n"
        + block
        + '\necho "FINAL_COUNT=${#PATHS[@]}"\n'
    )


def test_a_dropped_path_is_reported_not_silent(tmp_path):
    """The whole point: a drop must be VISIBLE. Silence here is the round-16 class."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    other = "docs/reference/kilo/OTHER.md"
    (r / other).write_text("no date\n", encoding="utf-8")
    p = _run(_wiring(f'"{rel}" "{other}"'), r)
    assert "DROPPED 1/2" in p.stderr, p.stdout + p.stderr
    assert "FINAL_COUNT=1" in p.stdout, "the undated path must still be staged"


def test_all_dropped_does_not_masquerade_as_an_empty_stage_list(tmp_path):
    """THE bug: helper exits 0 having dropped everything. The old `||` fallback never fired and
    PATHS silently became empty, so the script blamed the stage list for a guard decision."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    p = _run(_wiring(f'"{rel}"'), r)
    assert "DROPPED 1/1" in p.stderr, "an all-dropped run must SAY the guard dropped them"
    assert "FINAL_COUNT=0" in p.stdout
    assert "freshness-guard FAILED" not in p.stderr, "exit 0 is not a helper failure"


def test_a_helper_crash_keeps_the_unfiltered_list(tmp_path):
    """Fail-open: a broken guard must never stop the pipeline publishing."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    p = _run(_wiring(f'"{rel}"', guard_cmd="python3 -c 'import sys;sys.exit(3)'"), r)
    assert "freshness-guard FAILED" in p.stderr, p.stdout + p.stderr
    assert "FINAL_COUNT=1" in p.stdout, "the crash path must KEEP every candidate"


def test_paths_with_spaces_survive_the_round_trip(tmp_path):
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-09-02")
    spaced = "docs/reference/kilo/has space.md"
    (r / spaced).write_text("no date\n", encoding="utf-8")
    p = _run(_wiring(f'"{rel}" "{spaced}"'), r)
    assert "FINAL_COUNT=2" in p.stdout, p.stdout + p.stderr


def test_guard_reads_the_repo_it_is_told_to_not_a_hardcoded_root(tmp_path):
    """Finding 1: a hardcoded /opt/fabrik made the guard inspect the WRONG repo and fail open —
    the original incident reproduced WITH the fix installed."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    p = subprocess.run(
        [sys.executable, str(GUARD), rel],
        capture_output=True, text=True, cwd=str(r), env={"PATH": "/usr/bin:/bin"},
    )
    assert rel not in p.stdout.split(), "with CWD as the root the regression must be caught"
    assert "DROP" in p.stderr


def test_the_docstring_denominator_matches_the_real_stage_list():
    """The guard's coverage claim is DERIVED here, never trusted as written.

    It first read "7 of 13 static paths" because the count was taken off the shared WORKTREE,
    where a sibling held an uncommitted `scripts/service_catalog.json` line that never landed.
    A denominator asserted in prose is a denominator that drifts the moment the stage list moves —
    so re-derive both halves from the script itself and fail loudly on any divergence.
    """
    import re
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from guard_selection_freshness import head_text, refresh_date  # noqa: PLC0415

    repo = SCRIPTS.parent.parent
    sh = (SCRIPTS / "autocommit_pipeline_outputs.sh").read_text(encoding="utf-8")
    block = re.search(r"^PATHS=\(\n(.*?)^\)$", sh, re.S | re.M)
    assert block, "the static PATHS=( … ) array must be findable — the derivation depends on it"
    paths = [
        ln.strip() for ln in block.group(1).splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]

    # F4 — a GLOB or a VARIABLE in PATHS bypasses the guard entirely: the guard gets the literal
    # element, cannot stat it, fails OPEN, and `git add -- "$_p"` then expands it with git's own
    # wildmatch and stages every match unguarded. Proven end-to-end 2026-09-02. The denominator
    # counted such an entry as "undated", so the totals still matched and this test blessed it.
    for rel in paths:
        assert not (set("*?[]$\"'") & set(rel)), (
            f"stage path {rel!r} is not a literal — a glob or variable here bypasses the freshness "
            "guard completely and git expands it at `git add` time, staging unguarded files"
        )
        assert (repo / rel).is_file(), (
            f"stage path {rel!r} does not exist — a typo'd path contributes 0 to the dated count "
            "and would silently rebalance this denominator instead of failing"
        )

    # F8a — "guarded" is decided at HEAD, and ONLY at HEAD. `is_regression` compares worktree
    # against HEAD, so a doc dated only in the WORKTREE can never trigger the guard; requiring the
    # HEAD date alone already excludes it, which was F8a's whole point.
    # F9 (infra finding 01M1H1YPHN, 2026-09-03) — the earlier form ALSO required a worktree date,
    # and that extra term made this count sibling-dependent on a 3-session tree: all 12 staged paths
    # are pipeline-REGENERATED docs that are routinely dirty, so one sibling's uncommitted edit to a
    # `Last refresh:` line flipped the denominator and reddened an unrelated session's gate. Measured
    # live the day this landed: `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` was dirty. A guard
    # against worktree-derived counts must not itself count off the worktree.
    dated = sum(1 for rel in paths if refresh_date(head_text(rel, repo) or ""))

    doc = (SCRIPTS / "guard_selection_freshness.py").read_text(encoding="utf-8")
    claim = re.search(r"\*\*(\d+) of (\d+) static paths\*\*", doc)
    assert claim, "the docstring must state its static-path coverage as `N of M static paths`"
    assert (int(claim.group(1)), int(claim.group(2))) == (dated, len(paths)), (
        f"docstring claims {claim.group(1)} of {claim.group(2)} static paths; "
        f"the real stage list has {dated} dated of {len(paths)}"
    )

    undated = re.search(r"The (\d+) undated static paths", doc)
    assert undated, "the docstring must state how many static paths fail open"
    assert int(undated.group(1)) == len(paths) - dated, (
        f"docstring claims {undated.group(1)} undated; the stage list has {len(paths) - dated}"
    )

    # F5 — the docstring NAMES the undated files; grading only the number let a mutant swap in two
    # guarded files and three non-existent ones and still pass. The identity claim is the point of
    # the paragraph, so grade the identity.
    named = set(re.findall(r"`([^`]+)`", doc[undated.start() : undated.start() + 400]))
    # F9 — HEAD-only, for the same reason the count above is: this SET is sibling-dependent
    # otherwise, and a moved set fails the identity assert just as loudly as a moved number.
    derived = {rel for rel in paths if not refresh_date(head_text(rel, repo) or "")}
    # the docstring may name a file by basename; compare on basenames to stay readable
    assert {Path(n).name for n in named} >= {Path(d).name for d in derived}, (
        f"docstring names {sorted(named)} as the undated set; derived is {sorted(derived)}"
    )


def test_a_crashing_ai_render_helper_is_announced_not_silently_empty(tmp_path):
    """Review round 2, C2: the feeder used `< <(cmd || true)` — the exact pattern the comment four
    lines below it BANS. A crashing helper looked identical to "no packs qualified": PATHS gained
    nothing, the stage loop ran, and the FLEET-SYNCED ai packs silently stopped being committed."""
    wiring = """
set -u
PATHS=(existing.md)
_AI_OUT="$(mktemp)"
if python3 -c 'import sys; sys.exit(3)' > "$_AI_OUT"; then
  while IFS= read -r x; do [ -n "$x" ] && PATHS+=("$x"); done < "$_AI_OUT"
else
  echo "[autocommit] AI_RENDER_FAILED" >&2
fi
rm -f "$_AI_OUT"
echo "FINAL=${#PATHS[@]}"
"""
    p = _run(wiring, tmp_path)
    assert "AI_RENDER_FAILED" in p.stderr, "a crashing helper must be ANNOUNCED: " + p.stdout + p.stderr
    assert "FINAL=1" in p.stdout, "the crash must not silently wipe or grow PATHS"


def test_the_ai_render_denominator_is_graded_too(tmp_path):
    """Review round 2, C7: the docstring makes TWO coverage claims in one sentence — `N of M static
    paths` AND `N of M ai-render packs` — and only the static half was graded. The ungraded half is
    the one the docstring itself calls "the FLEET-SYNCED half, highest blast radius", so it is the
    half a silent drift hurts most. Independently raised by a pool finder in the same round."""
    import re
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from guard_selection_freshness import refresh_date  # noqa: PLC0415

    repo = SCRIPTS.parent.parent
    packs = sorted((repo / ".windsurf/rules/ai").glob("*.md"))
    assert packs, "precondition: the ai rules packs must exist for this to grade anything"
    dated = sum(
        1 for f in packs if refresh_date(f.read_text(encoding="utf-8-sig", errors="ignore"))
    )

    doc = (SCRIPTS / "guard_selection_freshness.py").read_text(encoding="utf-8")
    claim = re.search(r"\*\*(\d+) of\s+(\d+) ai-render packs\*\*", doc, re.S)
    assert claim, "the docstring must state its ai-render coverage as `N of M ai-render packs`"
    assert (int(claim.group(1)), int(claim.group(2))) == (dated, len(packs)), (
        f"docstring claims {claim.group(1)} of {claim.group(2)} ai-render packs; "
        f"the real pack set has {dated} dated of {len(packs)}"
    )

    undated = re.search(r"the (\d+) undated packs", doc)
    assert undated, "the docstring must state how many packs fail open"
    assert int(undated.group(1)) == len(packs) - dated, (
        f"docstring claims {undated.group(1)} undated packs; the real set has {len(packs) - dated}"
    )
