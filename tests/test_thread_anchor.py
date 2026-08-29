"""Behavior contract for the thread-anchor register (scripts/thread_anchor.py).

Why it exists, measured 2026-08-29 on one live session: 905 ``NEXT:`` lines emitted, ZERO read
back, and a thread carried by 85 consecutive NEXT: lines ("corpus audit — command N of 31") was
silently dropped the moment an operator question arrived — 10 NEXT: lines later it had vanished,
and nothing anywhere could notice. NEXT: was a single slot, write-only, and died at compaction.

The register fixes the MECHANISM, not the discipline: the Stop hook harvests what agents already
emit (no new obligation), and the prompt hooks re-inject open anchors the same way mail_notify.py
provably gets mail read. Every test here is a behavior an agent actually needs, not coverage.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "thread_anchor.py"


def run(args: list[str], stdin: str = "", env_dir: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True,
        env={"THREAD_ANCHOR_DIR": str(env_dir)} if env_dir else None,
    )
    return proc.returncode, proc.stdout


def harvest(text: str, d: Path, session: str = "s1") -> None:
    rc, _ = run(["harvest", "--session", session], stdin=text, env_dir=d)
    assert rc == 0


def line(d: Path, session: str = "s1") -> str:
    rc, out = run(["line", "--session", session], env_dir=d)
    assert rc == 0
    return out


# ── The founding defect, reproduced end to end ────────────────────────────────────────────────
def test_a_tangent_does_not_erase_a_long_running_anchor(tmp_path):
    """The live failure: 85 NEXT: lines carried the audit, one operator question wiped it."""
    harvest("done stuff\nNEXT: the corpus audit — command 14 of 31 — /fabrik-user-test", tmp_path)
    # The tangent: an operator question produces an unrelated NEXT.
    harvest("answered the CI question\nNEXT: disable the workflows in the three repos", tmp_path)
    out = line(tmp_path)
    assert "14 of 31" in out, f"the anchor died on a tangent — the exact founding defect: {out!r}"
    assert "three repos" in out, "the tangent's own NEXT must also survive as the latest successor"


def test_progress_updates_the_anchor_instead_of_stacking_duplicates(tmp_path):
    """'command 14 of 31' then 'command 15 of 31' is ONE thread advancing, not two threads."""
    harvest("NEXT: corpus audit — command 14 of 31", tmp_path)
    harvest("NEXT: corpus audit — command 15 of 31", tmp_path)
    out = line(tmp_path)
    assert "15 of 31" in out
    assert "14 of 31" not in out, f"stale progress stacked as a second anchor: {out!r}"


def test_plan_and_epic_paths_are_anchors(tmp_path):
    harvest("NEXT: resume docs/development/plans/2026-08-29-plan-1-thread.md phase B", tmp_path)
    harvest("NEXT: reply to fleet's mail", tmp_path)  # tangent
    assert "2026-08-29-plan-1-thread" in line(tmp_path)


def test_done_closes_an_anchor_and_silence_returns(tmp_path):
    harvest("NEXT: corpus audit — command 14 of 31", tmp_path)
    rc, _ = run(["done", "--session", "s1", "--match", "corpus audit"], env_dir=tmp_path)
    assert rc == 0
    out = line(tmp_path)
    assert "14 of 31" not in out, f"a closed anchor kept resurfacing: {out!r}"


def test_no_state_means_total_silence(tmp_path):
    """Anti-noise: an empty register must print NOTHING — a block that fires on every trivial
    turn becomes the wallpaper that killed CI."""
    assert line(tmp_path) == ""


def test_a_plain_next_is_not_promoted_to_an_anchor(tmp_path):
    """Ordinary successors roll; only long-running shapes persist. Without this, every turn
    mints an anchor and the injection becomes an unreadable scroll."""
    harvest("NEXT: fix the typo in the README", tmp_path)
    harvest("NEXT: answer the operator", tmp_path)
    out = line(tmp_path)
    assert "typo" not in out, f"a one-shot NEXT was promoted to an anchor: {out!r}"


def test_output_is_capped_at_four_lines(tmp_path):
    for i in range(9):
        harvest(f"NEXT: sweep {i} — item 1 of {20 + i}", tmp_path)
    out = line(tmp_path)
    assert 0 < len(out.strip().splitlines()) <= 6, out  # header + <=4 anchors + latest


def test_state_survives_a_new_process_and_is_session_scoped(tmp_path):
    """Disk, not context — this is the compaction survival. And session-scoped, because three
    concurrent sessions share this repo and must not see each other's threads."""
    harvest("NEXT: cert board TC3 of 12", tmp_path, session="a")
    assert "TC3" in line(tmp_path, session="a") or "3 of 12" in line(tmp_path, session="a")
    assert line(tmp_path, session="b") == "", "session b saw session a's threads"


def test_hook_mode_reads_session_from_stdin_json(tmp_path):
    """UserPromptSubmit/SessionStart pass a JSON payload on stdin, not a --session flag."""
    harvest("NEXT: epic docs/development/epics/2026-08-29-epic-9-sso.md ticket 2 of 7", tmp_path)
    rc, out = run(["line", "--hook"], stdin=json.dumps({"session_id": "s1"}), env_dir=tmp_path)
    assert rc == 0 and "epic-9-sso" in out, out


def test_harvest_is_failopen_on_garbage(tmp_path):
    """Wired into the Stop hook: a crash here would block every end-of-turn in ~46 repos."""
    rc, _ = run(["harvest", "--session", "s1"], stdin="\x00\xff not json not text \x00", env_dir=tmp_path)
    assert rc == 0


def test_a_reworded_suffix_does_not_mint_a_second_anchor(tmp_path):
    """Found live an hour after shipping: the injected block showed the SAME corpus-audit thread
    twice, because appending commentary ("… (now also held by the register)") changed the
    full-text key. Identity must rest on the anchor's PREFIX, where the stable subject lives."""
    harvest("NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test against the checklist", tmp_path)
    harvest("NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test against the checklist (now held by the register)", tmp_path)
    out = line(tmp_path)
    assert out.count("corpus audit") == 1, f"reworded suffix minted a duplicate anchor: {out!r}"


def test_done_and_line_never_block_on_an_open_stdin(tmp_path):
    """Found live: `done --match …` run from an agent's shell (stdin open, not a tty, nothing
    piped) hung forever in sys.stdin.read(). Only `harvest` and `--hook` consume stdin."""
    import subprocess as sp
    for args in (["done", "--session", "s1", "--match", "x"], ["line", "--session", "s1"]):
        proc = sp.Popen([sys.executable, str(SCRIPT), *args],
                        stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, text=True,
                        env={"THREAD_ANCHOR_DIR": str(tmp_path)})
        try:
            proc.communicate(timeout=5)  # stdin PIPE left open until communicate closes it
        except sp.TimeoutExpired:
            proc.kill()
            raise AssertionError(f"{args[0]} blocked on stdin")


def test_divergence_inside_the_prefix_window_still_dedupes(tmp_path):
    """Second live recurrence: truncating the key to 72 chars only helped when the texts
    diverged AFTER char 72 — "…/fabrik-user-test" vs "…/fabrik-user-test (held by the
    register…)" diverge at ~54 and duplicated again. The CLASS fix is containment: a new
    anchor whose key extends (or is extended by) an existing key is the same thread."""
    harvest("NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test", tmp_path)
    harvest("NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test (held by the register; resumes on your word)", tmp_path)
    harvest("NEXT: the corpus audit — command 15 of 31 — /fabrik-flows", tmp_path)
    out = line(tmp_path)
    assert out.count("corpus audit") == 1, f"still duplicating: {out!r}"
    assert "15 of 31" in out, "the newest progress must win"
