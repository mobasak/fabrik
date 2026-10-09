"""/fabrik-review queue — the text defects (D-711: a verdict showing the command text WRONG is edited).

Each test asserts the corrected sentence through its closing delimiter (an appended qualifier is a mutation), in
every file that carries it, and where the sentence describes a tool, drives that tool to show the behaviour the
sentence now states (the old text promised more than the tool does).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "commands" / "_sources" / "fabrik-review.md"
FRAG = REPO / "commands" / "_fragments"


def _norm(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def test_the_closing_pass_confirms_zero_defects_present_not_claims_executed_true() -> None:
    """Ledger claims state DEFECTS (STILL_TRUE = the defect persists), so 'every claim executed true' read as
    'every defect still there' (rows 1791354017, 1791146542) — in term-coverage and its term-edit mirror."""
    tc = _norm(FRAG / "term-coverage.md")
    te = _norm(FRAG / "term-edit.md")
    assert ("in which those seats RE-EXECUTED every claim of their slice ledgers and CONFIRMED zero code or doc "
            "defects present (none persisting, none the fix introduced) (D-206, D-335).") in tc
    assert ("the pass in which the round-1 seats re-executed every claim of their OWN slice ledgers and confirmed "
            "zero code or doc defects present — the same seat per slice") in te
    for t in (tc, te):
        assert "ledgers executed true" not in t


def test_a_fix_touched_slice_with_no_candidate_is_added_by_hand() -> None:
    """Row 1791235921: `next` builds slices only from the ids passed, so a slice whose file a fix edited but
    which raised nothing gets no ledger unless the lead adds it."""
    tc = _norm(FRAG / "term-coverage.md")
    assert ("a slice a fix hunk touched holds one even when it raised no candidate, and "
            "`review_loop_ledger.py next` builds slices only from the `--ids` passed, so add that slice's ledger "
            "by hand, one row per hunk — `{id: \"<slice>-X<n>\", file, line, claim: \"the fix hunk at <file:line> "
            "introduced a defect\"}`), or any claim") in tc
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import review_loop_ledger as rl
    finally:
        sys.path.pop(0)
    doc = {"candidates": [{"id": "A-1", "file": "a.py", "line": 3, "claim": "x"},
                          {"id": "B-1", "file": "b.py", "line": 9, "claim": "y"}]}
    assert [s["name"] for s in rl.next_ledger(doc, ["A-1"])] == ["A"], "slice B is built only when its id is passed"


def test_the_pre_pin_sweep_lists_the_pinned_literal_term_only(tmp_path: Path) -> None:
    """Rows 1790688796, 1790913510, 1791083066: `--claim` lists the literal term (case- and wrap-tolerant) in
    the --surface files, a directory walking only .md/.py — so a reworded mirror or another file type is not
    listed; the text now says so (term-coverage and its term-edit mirror) and orders the repo grep."""
    want = ("lists every line of the pinned surface where a rewritten claim's literal term occurs (case- and "
            "wrap-tolerant; a directory surface walks only its `.md` and `.py` files); a mirror outside the pin or "
            "in other words is not in that list, so also grep the repo for the term and two rewordings of the "
            "claim, and read each site before the pin")
    assert want in _norm(FRAG / "term-coverage.md")
    assert want in _norm(FRAG / "term-edit.md")
    for t in (_norm(FRAG / "term-coverage.md"), _norm(FRAG / "term-edit.md")):
        assert "lists every mirror site" not in t
    d = tmp_path / "pin"
    d.mkdir()
    (d / "a.md").write_text("alpha\nthe STOP\nkey fires here\n", encoding="utf-8")  # case + wrap
    (d / "b.py").write_text("# the stop key\n", encoding="utf-8")
    (d / "c.yaml").write_text("the stop key: 1\n", encoding="utf-8")
    (d / "e.md").write_text("the halt key triggers\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(REPO / "scripts" / "enforcement" / "check_review_hygiene.py"),
                        "--surface", "pin", "--claim", "stop key"],
                       cwd=tmp_path, capture_output=True, text=True, check=False)
    assert "a.md:2" in p.stdout and "b.py:1" in p.stdout, p.stdout
    assert "c.yaml" not in p.stdout and "e.md" not in p.stdout, p.stdout


def test_a_trimmed_round_one_sweeps_its_unread_slices_before_any_delta_pass() -> None:
    """Row 1790926480: round 1 is the only full pass, so unread slices were never 'next round' work —
    subagents-core and its term-edit mirror."""
    sc = _norm(FRAG / "subagents-core.md")
    te = _norm(FRAG / "term-edit.md")
    assert ("then the union is NOT the full pass: the receipt names the unread slices, and further full-pass waves "
            "over those slices alone run before any delta pass, since round 1 is not complete until every slice is "
            "read.") in sc
    assert ("then the union is NOT the full pass, the ledger names the unread slices and further full-pass waves "
            "over those slices alone run before any delta pass;") in te
    assert "re-sweeps them next round" not in sc and "the next round sweeps them first" not in te


def test_recorded_measured_carries_a_routed_out_of_round_defect() -> None:
    """Row 1790952423: receipts file a real out-of-hop or post-stop defect as RECORDED — measured, which the old
    definition ('making no code or doc claim') forbade; Phase 3's disposition list agrees."""
    t = _norm(SRC)
    assert ("executed and shown TRUE but not a defect this round fixes: a prevalence figure, or a real defect "
            "outside the round's bounded hop or past the scope-growth stop, its named destination in the reason "
            "(`term-coverage` D4). It never enters `unexecuted:`.") in t
    assert ("or it is `RECORDED — by design` with its owning row named, or — outside the round's bounded hop — "
            "`RECORDED — measured` with its destination.") in t
    assert "making no code or doc claim" not in t


def test_the_decision_row_lands_after_the_code_with_its_id_reserved_before_the_close() -> None:
    """Rows 1790187513, 1790232519: close-chain commits code first and the ledgers through the private index;
    `--reserve-id` holds the id durably, so it is reserved before the close."""
    t = _norm(SRC)
    assert ("mint its `docs/DECISIONS.md` row in the same change as the fix, classified at mint, its id reserved "
            "(`decisions.py --reserve-id`) before the close and the row committed after the code (close-chain's "
            "private-index step) —") in t
    assert "staged in the fix commit" not in t


def test_a_synced_path_matching_its_lock_entry_is_a_sync_write_never_reverted(tmp_path: Path) -> None:
    """Row 1790455114: on a re-vendor diff every synced file is in the diff by design. The lock entry tells a
    sync's write from a local edit; the check also passes with NO lock, so the text never says 'passes'."""
    import hashlib
    import json

    t = _norm(SRC)
    assert ("A synced path whose md5 equals its entry in the project's `.fabrik/synced.lock` is a sync's own write, "
            "not an edit: never revert it, and review only the repo's own files against it; with no lock, the rule "
            "above applies.") in t
    chk = [sys.executable, str(REPO / "scripts" / "enforcement" / "check_synced_unmodified.py"),
           "--project-root", str(tmp_path)]
    (tmp_path / "AGENTS.md").write_text("synced\n", encoding="utf-8")
    assert subprocess.run(chk, capture_output=True, text=True, check=False).returncode == 0, "no lock: passes"
    (tmp_path / ".fabrik").mkdir()
    md5 = hashlib.md5(b"synced\n", usedforsecurity=False).hexdigest()
    (tmp_path / ".fabrik" / "synced.lock").write_text(json.dumps({"AGENTS.md": md5}), encoding="utf-8")
    assert subprocess.run(chk, capture_output=True, text=True, check=False).returncode == 0, "matches its entry"
    (tmp_path / "AGENTS.md").write_text("edited\n", encoding="utf-8")
    assert subprocess.run(chk, capture_output=True, text=True, check=False).returncode == 1, "a local edit reds"


def test_the_gate_scope_sentence_states_the_ruff_scope_and_points_at_the_reference() -> None:
    """Row 1790907152: code pushed before the review is never linted by the ruff leg (staged + unpushed only);
    the rest of the gate's scoping is CLAUDE.md's to state, so this sentence no longer restates it."""
    t = _norm(SRC)
    assert ("`final_gate` takes no surface argument and scopes each check its own way (CLAUDE.md § Completion "
            "Contract 2); its ruff leg lints only staged changes and unpushed commits, so code pushed before the "
            "review is linted by running ruff on its paths by hand. On a shared tree a check that reads beyond your "
            "change can red on another lane's work, and") in t
    assert "every other check reads whole directories" not in t
