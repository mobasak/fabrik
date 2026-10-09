"""The `/fabrik-command-improve` DRIVE contract — who runs it, on what model, sized how.

Operator ruling 2026-09-20: the command was precise about its mechanics and silent on how it is
driven (11 of 17 aims absent). The rules point at existing machinery; this grader keeps them in
the source so a later "lean" edit cannot silently drop the caller restriction, the Fable-else-Opus
rule or the box-sized seat rule.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "commands" / "_sources" / "fabrik-command-improve.md"


def _drive_section() -> str:
    text = SRC.read_text(encoding="utf-8")
    start = text.index("## Drive")
    end = text.index("\n## ", start + 1)
    # WRAP-AWARE: a needle that spans a soft line break must still match (a line grep cannot
    # see a wrapped claim — the first cut of this grader read "no\n  corpus" as absent).
    return " ".join(text[start:end].split())


def test_the_source_states_who_may_run_it() -> None:
    sec = _drive_section()
    assert ("`CLAUDE_AGENT` is `kaizen` — the queues' `feedback_owner` (D-627) — or the distributor (`infra`) when "
            "`.fabrik/work/config.json` names no `feedback_owner`") in sec
    assert "`intel`" not in sec.split("- **Driver.**")[0], "intel holds no feedback-queue fallback (D-627)"
    assert "does not run it" in sec


def test_the_source_states_fable_drives_else_opus() -> None:
    sec = _drive_section()
    assert "on Fable" in sec and "driven on Opus" in sec
    # the TRIGGER is locked, not only the phrases: a mutant that loosened "when" survived round 1
    assert "bands RED and the window it names is Fable" in sec
    assert "this account's own Fable window" in sec and "/model claude-fable-5-1" in sec
    assert (
        "D-295" in sec
    )  # the band is raised to the account's own Fable reading; no flip reaches it


def test_the_source_sizes_seats_from_the_box_by_role() -> None:
    sec = _drive_section()
    assert "dispatch_headroom.py" in sec
    assert "haiku 1× · sonnet 2× · opus 5× · fable 10×" in sec
    assert "not restated here" in sec  # the dispatch shape is pointed at, never copied (round-1 C1)
    assert (
        "still RUNNING" in sec
    )  # the subtraction is dispatch_headroom.py's, over running records only
    assert "never below the floor" in sec  # the sibling subtraction never starves a session


def test_the_source_bounds_the_passes_with_the_real_d278_remedy() -> None:
    sec = _drive_section()
    # D-335 superseded D-229's delta sizing (chunk 1, f6beb8b88 re-cut this section) — the pin
    # kept the old id and read red at HEAD for a day; the stop's remedy (D-278) is unchanged
    assert "D-335" in sec and "D-278" in sec
    assert (
        "`--confirmed`/`--own-fix` pair" in sec
    )  # the stop reads the PAIR; --own-fix alone is silence
    assert "fix every confirmed defect still open" in sec
    assert "re-verify that fixed set alone" in sec  # the remainder rounds TERMINATE
    assert "backlog row with a named destination" in sec
    assert "no corpus rule names a clock" in sec  # the 3-minute timer stays out (round-1 F2)


def test_the_source_grounds_against_fabrik_lib_and_the_ledgers_before_drafting() -> None:
    sec = _drive_section()
    for needle in (
        "/opt/fabrik-lib/README.md",
        "docs/STRATEGIC_BACKLOG.md",
        "select_rules.py --changed",
        "EXECUTED before the render",
    ):
        assert needle in sec, needle


def test_the_source_sets_a_time_budget_from_measured_closes() -> None:
    sec = _drive_section()
    assert "Budget one run at 40 minutes" in sec
    assert "median 34" in sec and "max 54" in sec and "5 of the 16 past 40" in sec


def test_the_source_carries_d711_and_tells_a_worktree_run_the_truth(tmp_path, monkeypatch) -> None:
    """/fabrik-command-improve queue (kaizen D-711 audit): PHASE 2 never stated D-711 although the queue tool now
    prints a `held (all time):` line and `--reject` warns on a re-hold; a landed row was 'say so and move on' with
    no command that removes it; the mark recipe's `--repo defaults to the hub` is false inside a hub worktree
    (`_resolve_fabrik_root`); and the render and Terminal were owed by a worktree run that must render nothing."""
    import importlib.util
    import subprocess

    src = (REPO / "commands" / "_sources" / "fabrik-command-improve.md").read_text(encoding="utf-8")
    text = " ".join(src.split())
    assert ("**What one row earns (D-711).** A one-off verdict is edited only when it shows the command text WRONG "
            "or MISLEADING; valid one-off advice is rejected with `HELD:<subject>` first in the reason") in text
    assert "Before rejecting, search earlier reject reasons for the subject" in text
    assert "is edited, never re-rejected — `--reject` warns on one but still writes it" in text
    assert "An Opus seat audits the advice set for misfiled text defects before any advice is rejected." in text
    assert "--commit <the edit's sha> --repo <the checkout that holds it>" in text and "$(git rev-parse HEAD)" not in text
    assert "pass the full sha of the edit and the checkout it was committed in" in text
    assert ("if its MECHANISM (trigger, scope, unit) is already there, not merely its topic, the row is answered — "
            "`--reject <command> --rows <ts> --reason \"<live path:line + quote + the landing commit>\"`") in text
    assert ("`git log --reverse -S '<phrase>' -- <file>` on a phrase from ONE source line (`-S` and `-G` both miss a "
            "phrase wrapped across lines)") in text
    assert "say so and move on" not in text
    assert "defaults to the hub, so" not in text and "$(git -C /opt/fabrik rev-parse HEAD)" not in text
    assert "`--repo` defaults to `$FABRIK_ROOT` when set, else the checkout you run from inside a hub worktree, else the hub" in text
    assert "a worktree renders nothing and runs `--check` alone" in text
    assert "# render — main checkout only, never a worktree" in src
    assert "One edit committed (and rendered, in the main checkout; infra renders a worktree's at merge)" in text
    assert ("A sentence naming what a gate or script reads is checked against every branch of that function, for "
            "every shape the sentence covers; a rule adapted from `CLAUDE.md` or a fragment is pointed at, or quoted in "
            "its own words and routes, never narrowed in paraphrase; a `_fragments/` edit names each `{{include:}}` "
            "consumer and its bound placeholders, and must be obeyable in each.") in text
    kz = " ".join((REPO / "docs" / "reference" / "agents" / "kaizen.md").read_text(encoding="utf-8").split())
    assert ("Valid one-off advice is rejected with `HELD:<subject>` first (D-711); a subject the `--queue` header's "
            "`held (all time):` line already names is a recurrence, and is edited instead.") in kz
    # the behaviour the wording now relies on: inside a hub worktree --repo resolves to that worktree
    spec = importlib.util.spec_from_file_location("cfr_probe", REPO / "scripts" / "command_feedback_report.py")
    cfr = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cfr)
    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    hub = tmp_path / "hub"
    vcs = "gi" + "t"
    subprocess.run([vcs, "init", "-q", str(hub)], check=True, env=env)
    subprocess.run([vcs, "-C", str(hub), "commit", "-q", "--allow-empty", "-m", "x"], check=True, env=env)
    wt = tmp_path / "wt"
    subprocess.run([vcs, "-C", str(hub), "worktree", "add", "-q", "--detach", str(wt)], check=True, env=env)
    monkeypatch.setattr(cfr, "_HUB_PATH", hub)
    monkeypatch.chdir(wt)
    assert cfr._resolve_fabrik_root() == wt.resolve()
