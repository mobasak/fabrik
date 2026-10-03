"""Tests for `command_feedback_report.py --lane` — the lane's 30-day measures and kill-rule joins
(plan 2026-10-02-plan-1 T06; spec 2026-10-02-fabrik-task-feature-lane-design § Validation, § D9).

Every test drives the real script as a subprocess over a fixture feedback ledger and the refusal
ledger beside it (`lane-refusals.jsonl`, the D9 location: the state dir's parent, which is the
feedback ledger's own directory)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_feedback_report.py"
T0 = time.time() - 3600


def _row(cmd: str, *, ts: float = T0, wall: float = 600.0, v1: bool = False, **kw) -> dict:
    """A feedback row. A `fabrik-task` row is a v2 close (it carries the `over_appetite` key every
    v2 close writes) unless `v1=True`."""
    base = {
        "ts": ts,
        "sid": "s1",
        "repo": "/opt/x",
        "command": cmd,
        "state": "done",
        "wall_s": wall,
        "rounds": 1,
        "agent": "infra",
        "surface": "",
    }
    if cmd == "fabrik-task" and not v1:
        base["over_appetite"] = "no"
    base.update(kw)
    return base


def _refusal(rid: str, *, ts: float = T0, **kw) -> dict:
    base = {"id": rid, "ts": ts, "session": "s1", "repo": "/opt/x/.git", "why": "A vs B"}
    base.update(kw)
    return base


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _lane(tmp: Path, rows: list[dict], refusals: list[dict] | None = None, *args: str):
    ledger = tmp / "command-feedback.jsonl"
    _write(ledger, rows)
    if refusals is not None:
        _write(tmp / "lane-refusals.jsonl", refusals)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--ledger", str(ledger), "--lane", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _doc(tmp: Path, rows: list[dict], refusals: list[dict] | None = None, *args: str) -> dict:
    p = _lane(tmp, rows, refusals, "--json", *args)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


# ── Behaviour 1: per-agent refused and downgraded shares; the ratio excludes downgraded specs ──


def test_lane_prints_per_agent_refused_and_downgraded_shares(tmp_path: Path) -> None:
    rows = [
        # infra: two admitted lane starts, one of them the DOWNGRADE restart of LR-a
        _row("fabrik-task", from_downgrade="LR-a"),
        _row("fabrik-task"),
        # intel: one admitted start
        _row("fabrik-task", agent="intel", sid="s9"),
    ]
    refusals = [
        _refusal("LR-a", agent="infra"),
        _refusal("LR-b", agent="infra"),
        _refusal("LR-c", agent="intel"),
    ]
    doc = _doc(tmp_path, rows, refusals)
    assert doc["agents"]["infra"] == {"starts": 4, "refused": 2, "downgraded": 1}
    assert doc["agents"]["intel"] == {"starts": 2, "refused": 1, "downgraded": 0}
    text = _lane(tmp_path, rows, refusals).stdout
    assert "  infra · 4 · 2/4 (50%) · 1/2 (50%)" in text.splitlines()
    assert "  intel · 2 · 1/2 (50%) · 0/1 (0%)" in text.splitlines()


def test_lane_attributes_an_agentless_refusal_through_its_session(tmp_path: Path) -> None:
    """The D9 row names the session, not necessarily the agent: the session's feedback rows do."""
    rows = [_row("fabrik-task", agent="fleet", sid="s7")]
    doc = _doc(tmp_path, rows, [_refusal("LR-z", session="s7"), _refusal("LR-y", session="s?")])
    assert doc["agents"]["fleet"] == {"starts": 2, "refused": 1, "downgraded": 0}
    assert doc["agents"]["?"] == {"starts": 1, "refused": 1, "downgraded": 0}


def test_lane_task_to_spec_ratio_excludes_the_downgraded_spec_run(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", sid="s1", from_downgrade="LR-a"),  # DOWNGRADE
        _row("fabrik-spec", ts=T0 - 50, state="done", sid="s2"),
        _row("fabrik-spec", ts=T0 - 40, state="done", sid="s3"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a", sid="s1"),
        _row("fabrik-task", ts=T0 + 990, sid="s4"),
    ]
    doc = _doc(tmp_path, rows, [_refusal("LR-a")])
    assert doc["task_to_spec"] == {
        "task": 2,
        "spec": 3,
        "downgraded_spec": 1,
        "unjoined_downgrades": 0,
        "ratio": 1.0,
    }
    text = _lane(tmp_path, rows, [_refusal("LR-a")]).stdout
    assert (
        "task-to-spec: 2 task / 2 spec = 1.0 (1 downgraded /fabrik-spec run excluded of 3)"
        in text.splitlines()
    )


def test_lane_an_id_less_handoff_never_joins_whatever_its_timing_or_repo(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0 + 800, state="handoff"),
        _row("fabrik-spec", ts=T0, state="handoff"),  # before the task started, same session
        _row("fabrik-spec", ts=T0, state="handoff", repo="/opt/other"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
    ]
    tts = _doc(tmp_path, rows, [])["task_to_spec"]
    assert (tts["downgraded_spec"], tts["unjoined_downgrades"]) == (0, 1)


def test_lane_one_spec_handoff_is_excluded_once_for_two_downgraded_tasks(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", from_downgrade="LR-a"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
        _row("fabrik-task", ts=T0 + 1900, wall=300, from_downgrade="LR-b"),
    ]
    tts = _doc(tmp_path, rows, [])["task_to_spec"]
    assert (tts["downgraded_spec"], tts["unjoined_downgrades"]) == (1, 1)


# ── Behaviour 2: task median, UPGRADE share with its token split, downgrade-then-upgrade ──


def test_lane_task_median_upgrade_share_and_downgrade_then_upgrade(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-task", wall=600, upgrade="contract", upgrades="contract new-source"),
        _row(
            "fabrik-task",
            wall=1200,
            from_downgrade="LR-a",
            upgrade="behaviours",
            upgrades="behaviours",
        ),
        _row("fabrik-task", wall=1800, from_downgrade="LR-b"),
        _row("fabrik-task", wall=6000, upgrade="sync"),
        _row("fabrik-review", wall=99999),  # another command never moves the task median
    ]
    t = _doc(tmp_path, rows, [])["task"]
    assert t["rows"] == 4
    assert t["median_min"] == 25  # (1200 + 1800) / 2 s
    assert t["upgraded"] == 3
    assert t["upgrade_tokens"] == {"behaviours": 1, "contract": 1, "new-source": 1, "sync": 1}
    assert (t["from_downgrade"], t["downgrade_then_upgrade"]) == (2, 1)
    text = _lane(tmp_path, rows, []).stdout
    assert (
        "task: median 25 min of 4 · UPGRADE 3/4 (75%) [behaviours 1 · contract 1 · new-source 1"
        " · sync 1]"
        " · downgraded-then-upgraded 1/2 (50%)" in text.splitlines()
    )


def test_lane_no_rows_prints_no_phantom_zero_median(tmp_path: Path) -> None:
    doc = _doc(tmp_path, [], None)
    assert doc["task"]["median_min"] is None
    assert doc["in_lane_review"]["median_min"] is None
    text = _lane(tmp_path, [], None).stdout
    assert "task: median — min of 0 · UPGRADE —/0 · downgraded-then-upgraded —/0" in text
    untimed = _lane(tmp_path, [_row("fabrik-task", wall="x"), _row("fabrik-task", wall=120)]).stdout
    assert "task: median 2 min of 1 [+1 untimed] · UPGRADE 0/2 (0%)" in untimed


# ── Behaviour 3: the in-lane full-review median reads parent: fabrik-task rows only ──


def test_lane_in_lane_full_review_median_uses_only_parent_fabrik_task(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-review", wall=600, parent="fabrik-task"),
        _row("fabrik-review", wall=1800, parent="fabrik-task"),
        _row("fabrik-review", wall=36000),  # a standalone full review
        _row("fabrik-review", wall=36000, parent="fabrik-execute-plan"),
        _row("fabrik-review-scoped", wall=60, parent="fabrik-task"),  # not a FULL review
    ]
    r = _doc(tmp_path, rows, [])["in_lane_review"]
    assert r == {"rows": 2, "timed": 2, "median_min": 20}
    assert "in-lane full review: median 20 min of 2" in _lane(tmp_path, rows, []).stdout


# ── Behaviour 4: a small spec sent back to spec-review, never to plan-review ──

SPEC = "docs/superpowers/specs/2026-10-02-foo-design.md"


def test_lane_small_spec_sent_back_counts_spec_review_only(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, size="small", surface=SPEC),
        _row("fabrik-plan-review", ts=T0 + 10, surface=f"plan + {SPEC}"),
        _row(
            "fabrik-spec",
            ts=T0,
            size="small",
            surface="docs/superpowers/specs/2026-10-02-bar-design.md",
        ),
        _row(
            "fabrik-spec-review",
            ts=T0 + 20,
            surface="/opt/x/docs/superpowers/specs/2026-10-02-bar-design.md",
        ),
    ]
    s = _doc(tmp_path, rows, [])["small_specs"]
    assert s == {"rows": 2, "unkeyed": 0, "sent_back": 1}
    assert "small specs sent back to spec-review: 1/2 (50%)" in _lane(tmp_path, rows, []).stdout


def test_lane_small_spec_review_must_follow_in_the_same_repo(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, size="small", surface=SPEC),
        _row("fabrik-spec-review", ts=T0 - 10, surface=SPEC),  # BEFORE the spec closed
        _row("fabrik-spec-review", ts=T0 + 10, surface=SPEC, repo="/opt/other"),
        _row("fabrik-spec-review", ts=T0 + 10, surface=SPEC.replace("foo", "xfoo")),
        _row("fabrik-spec-review", ts=T0 + 10, surface=SPEC.replace("specs/", "specs/old-")),
        _row("fabrik-spec", ts=T0, size="medium", surface=SPEC.replace("foo", "baz")),
    ]
    assert _doc(tmp_path, rows, [])["small_specs"] == {"rows": 1, "unkeyed": 0, "sent_back": 0}


def test_lane_a_small_spec_with_no_spec_path_leaves_the_denominator(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", size="small", surface="the idea"),
        _row("fabrik-spec", ts=T0, size="small", surface=SPEC),
        _row("fabrik-spec-review", ts=T0 + 10, surface=SPEC, repo="/opt/x/.claude/worktrees/w"),
    ]
    assert _doc(tmp_path, rows, [])["small_specs"] == {"rows": 2, "unkeyed": 1, "sent_back": 1}
    assert (
        "small specs sent back to spec-review: 1/1 (100%) [+1 with no spec path in surface]"
        in _lane(tmp_path, rows, []).stdout.splitlines()
    )


@pytest.mark.parametrize(
    "size", ["small", "Small", "SMALL", "  small  ", "small (≈300 lines, 3 files)"]
)
def test_lane_size_small_reads_five_legitimate_spellings(tmp_path: Path, size: str) -> None:
    rows = [_row("fabrik-spec", size=size, surface=SPEC)]
    assert _doc(tmp_path, rows, [])["small_specs"]["rows"] == 1


@pytest.mark.parametrize("size", ["smallish", "not small", "medium", "", "large small"])
def test_lane_size_small_refuses_lookalikes(tmp_path: Path, size: str) -> None:
    rows = [_row("fabrik-spec", size=size, surface=SPEC)]
    assert _doc(tmp_path, rows, [])["small_specs"]["rows"] == 0


# ── Behaviour 5: the over-appetite share from phase_marks, never `phases`; pins per repo ──


def test_lane_over_appetite_share_reads_phase_marks_never_phases(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-execute-plan", phases=9, over_appetite_phases="1", phase_marks="4"),
        _row("fabrik-execute-plan", phases=9, over_appetite_phases="0", phase_marks="1"),
        _row("fabrik-execute-plan", phases=9),  # predates D11: in no bucket
        _row("fabrik-execute-plan", phases=9, over_appetite_phases="x", phase_marks="2"),
        _row("fabrik-execute-plan", phases=9, over_appetite_phases="3", phase_marks="2"),
    ]
    a = _doc(tmp_path, rows, [])["over_appetite"]
    assert a == {"rows": 2, "phase_marks": 5, "over_appetite_phases": 1, "unreadable": 2}
    assert (
        "over-appetite: 1/5 phase marks (20%) over 2 rows [+2 unreadable]"
        in _lane(tmp_path, rows, []).stdout
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=30,
    )


def test_lane_counts_lane_json_pins_per_repo(tmp_path: Path) -> None:
    committed, absent, loose = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    for repo in (committed, absent, loose):
        repo.mkdir()
        _git(repo, "init", "-q")
    (committed / ".fabrik").mkdir()
    (committed / ".fabrik" / "lane.json").write_text('{"version": 2}\n')
    _git(committed, "add", ".fabrik/lane.json")
    _git(committed, "commit", "-q", "-m", "lane v2")
    sha = subprocess.run(
        ["git", "-C", str(committed), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    (loose / ".fabrik").mkdir()
    (loose / ".fabrik" / "lane.json").write_text('{"version": 1}\n')  # pinned v1, uncommitted
    led = tmp_path / "led"
    led.mkdir()
    rows = [
        _row("fabrik-task", repo=str(committed)),
        _row("fabrik-task", repo=str(committed)),
        _row("fabrik-task", repo=str(absent)),
        _row("fabrik-task", repo=str(loose)),
        _row("fabrik-task", repo=str(tmp_path / "gone")),
        _row("fabrik-task", repo=""),
        _row("fabrik-task", repo="/opt/\x00bad"),  # a hand-edited cell never crashes the view
    ]
    pins = _doc(led, rows, [])["pins"]
    assert pins["repos"] == 5
    assert pins["pinned"] == [
        {"repo": str(committed), "version": 2, "commit": sha, "warning": None},
        {"repo": str(loose), "version": 1, "commit": None, "warning": None},
    ]
    text = _lane(led, rows, []).stdout.splitlines()
    assert "lane.json pins: 2 of 5 repos" in text
    assert f"  {committed} v2 @{sha[:12]}" in text
    assert f"  {loose} v1 uncommitted" in text


def test_lane_an_invalid_lane_json_is_a_pin_with_its_warning(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / ".fabrik").mkdir(parents=True)
    (repo / ".fabrik" / "lane.json").write_text('{"version": "2"}')
    led = tmp_path / "led"
    led.mkdir()
    pinned = _doc(led, [_row("fabrik-task", repo=str(repo))], [])["pins"]["pinned"]
    assert len(pinned) == 1 and pinned[0]["version"] == 2  # the default (D-507)
    assert "lane.json" in pinned[0]["warning"]


def test_lane_pins_read_unknown_when_task_lane_cannot_load(tmp_path: Path) -> None:
    """A copy of the script with no `task_lane.py` beside it prints `unknown`, never `0 of N`."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / SCRIPT.name).write_bytes(SCRIPT.read_bytes())
    ledger = tmp_path / "command-feedback.jsonl"
    _write(ledger, [_row("fabrik-task")])
    p = subprocess.run(
        [sys.executable, str(scripts / SCRIPT.name), "--ledger", str(ledger), "--lane"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert p.returncode == 0, p.stderr
    assert "lane.json pins: unknown — task_lane.py unavailable (1 repos)" in p.stdout.splitlines()
    assert "task_lane unavailable" in p.stderr


# ── the mode's own boundaries ──


@pytest.mark.parametrize(
    "extra",
    [
        ["--command", "fabrik-task"],
        ["--agent", "infra"],
        ["--queue", "x"],
        ["--stages"],
        ["--observer-rank"],
    ],
)
def test_lane_refuses_a_filter_or_another_mode(tmp_path: Path, extra: list[str]) -> None:
    p = _lane(tmp_path, [_row("fabrik-task")], [], *extra)
    assert p.returncode == 2
    assert "--lane" in p.stderr


def test_lane_since_windows_both_ledgers(tmp_path: Path) -> None:
    old = time.time() - 40 * 86400
    rows = [_row("fabrik-task"), _row("fabrik-task", ts=old)]
    refusals = [_refusal("LR-a"), _refusal("LR-b", ts=old)]
    doc = _doc(tmp_path, rows, refusals, "--since", "30")
    assert doc["agents"]["infra"] == {"starts": 2, "refused": 1, "downgraded": 0}
    assert doc["coverage"]["feedback_rows"] == 1
    assert doc["coverage"]["refusal_rows"] == 1


def test_lane_a_missing_refusal_ledger_and_corrupt_lines_never_crash(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(ledger, [_row("fabrik-task", wall="NaN", upgrades=7, from_downgrade=None)])
    (tmp_path / "lane-refusals.jsonl").write_text(
        f'not json\n[1]\n{{"id": "LR-q", "ts": {time.time()!r}}}\n'
    )
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--ledger", str(ledger), "--lane", "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert p.returncode == 0, p.stderr
    doc = json.loads(p.stdout)
    assert doc["coverage"]["refusal_rows"] == 1
    assert doc["task"]["rows"] == 1 and doc["task"]["timed"] == 0
    assert doc["agents"]["?"]["refused"] == 1


# ── review round 1 (T06-O1..O12, S1..S3) ──


def test_lane_exact_from_downgrade_on_the_spec_row_joins_first(tmp_path: Path) -> None:
    """T06-O3, T08-D7 C-O2: the spec handoff row carrying the id is the downgrade, whatever its
    timing; the id-less handoff is NOT given to the task whose id no spec row carries."""
    rows = [
        _row("fabrik-spec", ts=T0 + 800, state="handoff", surface="a", from_downgrade="LR-a"),
        _row("fabrik-spec", ts=T0, state="handoff", surface="b"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
        _row("fabrik-task", ts=T0 + 1000, wall=300, from_downgrade="LR-b"),
    ]
    tts = _doc(tmp_path, rows, [])["task_to_spec"]
    assert (tts["downgraded_spec"], tts["unjoined_downgrades"]) == (1, 1)


def test_lane_an_id_carrying_spec_is_never_inferred_for_another_task(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", surface="a", from_downgrade="LR-z"),
        _row("fabrik-spec", ts=T0, state="done", surface="c"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-c"),
    ]
    tts = _doc(tmp_path, rows, [])["task_to_spec"]
    assert (tts["spec"], tts["downgraded_spec"], tts["unjoined_downgrades"]) == (2, 1, 1)


def test_lane_two_specs_two_tasks_each_spec_claimed_once(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", surface="A", from_downgrade="LR-a"),
        _row("fabrik-spec", ts=T0 + 10, state="handoff", surface="B", from_downgrade="LR-b"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
        _row("fabrik-task", ts=T0 + 950, wall=300, from_downgrade="LR-b"),
    ]
    assert _doc(tmp_path, rows, [])["task_to_spec"]["downgraded_spec"] == 2


def test_lane_a_done_spec_is_never_a_downgrade(tmp_path: Path) -> None:
    """Only a HANDOFF row carries a downgrade: a done row with the id is no downgrade."""
    rows = [
        _row("fabrik-spec", ts=T0, state="done", surface="A", from_downgrade="LR-a"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
    ]
    tts = _doc(tmp_path, rows, [])["task_to_spec"]
    assert (tts["downgraded_spec"], tts["unjoined_downgrades"]) == (0, 1)


def test_lane_counts_distinct_specs_not_spec_rows(tmp_path: Path) -> None:
    """T06-O1: a handoff and a done close of ONE spec are one spec, in both ratio terms."""
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", surface=SPEC, from_downgrade="LR-a"),
        _row(
            "fabrik-spec", ts=T0 + 5, state="done", surface=SPEC, repo="/opt/x/.claude/worktrees/w"
        ),
        _row("fabrik-spec", ts=T0, state="done", surface="other"),
        _row("fabrik-spec", ts=T0, state="done"),
        _row("fabrik-spec", ts=T0, state="done"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
    ]
    tts = _doc(tmp_path, rows, [])["task_to_spec"]
    assert (tts["spec"], tts["downgraded_spec"], tts["ratio"]) == (4, 1, 0.33)


def test_lane_small_specs_count_distinct_specs(tmp_path: Path) -> None:
    """T06-O4: a small spec closed twice is one small spec, sent back once."""
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", size="small", surface=SPEC),
        _row("fabrik-spec", ts=T0 + 5, size="small", surface=SPEC),
        _row("fabrik-spec-review", ts=T0 + 10, surface=SPEC),
    ]
    assert _doc(tmp_path, rows, [])["small_specs"] == {"rows": 1, "unkeyed": 0, "sent_back": 1}


def test_lane_spec_review_at_the_same_instant_is_not_after(tmp_path: Path) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, size="small", surface=SPEC),
        _row("fabrik-spec-review", ts=T0, surface=SPEC),
    ]
    assert _doc(tmp_path, rows, [])["small_specs"]["sent_back"] == 0


def test_lane_worktree_paths_collapse_to_their_main_checkout(tmp_path: Path) -> None:
    """T06-O2: three worktrees of one repo are one repo."""
    rows = [
        _row("fabrik-task", repo="/opt/x"),
        _row("fabrik-task", repo="/opt/x/.claude/worktrees/a"),
        _row("fabrik-task", repo="/opt/x/.claude/worktrees/b/"),
        _row("fabrik-task", repo="/opt/xy"),
    ]
    assert _doc(tmp_path, rows, [])["pins"]["repos"] == 2


def test_lane_v1_task_rows_leave_the_lane_denominator(tmp_path: Path) -> None:
    """T06-O5: a task closed before v2 carries no `over_appetite` key and is no lane start."""
    rows = [_row("fabrik-task"), _row("fabrik-task", v1=True), _row("fabrik-task", v1=True)]
    doc = _doc(tmp_path, rows, [_refusal("LR-a", agent="infra")])
    assert doc["agents"]["infra"] == {"starts": 2, "refused": 1, "downgraded": 0}
    assert doc["coverage"]["v1_task_rows"] == 2
    assert "2 v1 fabrik-task rows excluded from lane starts" in _lane(tmp_path, rows, []).stdout


def test_lane_defaults_to_a_thirty_day_window_and_says_so(tmp_path: Path) -> None:
    """T06-O6."""
    old = time.time() - 31 * 86400
    rows = [_row("fabrik-task"), _row("fabrik-task", ts=old)]
    doc = _doc(tmp_path, rows, [_refusal("LR-a", ts=old)])
    assert doc["coverage"]["window_days"] == 30
    assert (doc["coverage"]["feedback_rows"], doc["coverage"]["refusal_rows"]) == (1, 0)
    head = _lane(tmp_path, rows, []).stdout.splitlines()[0]
    assert head.startswith("lane report — last 30 days — 1 feedback rows")
    assert _doc(tmp_path, rows, [], "--since", "40")["coverage"]["window_days"] == 40


@pytest.mark.parametrize("flag", ["--rows", "--commit"])
def test_lane_refuses_rows_and_commit_naming_the_flag(tmp_path: Path, flag: str) -> None:
    """T06-O7."""
    p = _lane(tmp_path, [_row("fabrik-task")], [], flag, "x")
    assert p.returncode == 2
    last = p.stderr.strip().splitlines()[-1]
    assert flag in last and "--lane" in last
    other = "--commit" if flag == "--rows" else "--rows"
    assert other not in last


def test_lane_token_tally_falls_back_to_the_single_upgrade(tmp_path: Path) -> None:
    """T06-O8: every upgraded row has at least one token, so the share and the dict agree."""
    rows = [
        _row("fabrik-task", upgrade="sync"),
        _row("fabrik-task", upgrade="contract", upgrades=""),
        _row("fabrik-task", upgrade="contract", upgrades="contract appetite"),
        _row("fabrik-task"),
    ]
    t = _doc(tmp_path, rows, [])["task"]
    assert t["upgraded"] == 3
    assert t["upgrade_tokens"] == {"appetite": 1, "contract": 2, "sync": 1}


def test_lane_undated_refusals_are_disclosed_not_dropped_silently(tmp_path: Path) -> None:
    """T06-O12."""
    refusals = [_refusal("LR-a"), {"id": "LR-b"}, {"id": "LR-c", "ts": "soon"}]
    doc = _doc(tmp_path, [_row("fabrik-task")], refusals)
    assert (doc["coverage"]["refusal_rows"], doc["coverage"]["undated_refusals"]) == (1, 2)
    assert "1 refusal rows [+2 undated]" in _lane(tmp_path, [], refusals).stdout


@pytest.mark.parametrize(
    ("marks", "over", "counted"),
    [("3", "3", True), ("3", "4", False), (True, 0, False), (3, False, False), (2, 1, True)],
)
def test_lane_appetite_boundaries(
    tmp_path: Path, marks: object, over: object, counted: bool
) -> None:
    """op == pm is readable; a bool is never a count (T06-S1, S2, O9)."""
    rows = [_row("fabrik-execute-plan", phase_marks=marks, over_appetite_phases=over)]
    a = _doc(tmp_path, rows, [])["over_appetite"]
    assert (a["rows"], a["unreadable"]) == ((1, 0) if counted else (0, 1))


def test_lane_a_failed_task_lane_import_warns_once(tmp_path: Path) -> None:
    """T06-S3: the failure is cached — one warning, however many times the loader is asked."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / SCRIPT.name).write_bytes(SCRIPT.read_bytes())
    (scripts / "task_lane.py").write_text("raise ImportError('broken')\n")
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('r', {str(scripts / SCRIPT.name)!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "print(m._task_lane(), m._task_lane(), m._task_lane())\n"
    )
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert p.stdout.strip() == "None None None", p.stderr
    assert p.stderr.count("task_lane unavailable") == 1


def test_lane_a_refusal_is_downgraded_by_its_spec_handoff_alone(tmp_path: Path) -> None:
    """The `/fabrik-spec` DOWNGRADE handoff carries the id even before the task closes."""
    rows = [_row("fabrik-spec", state="handoff", from_downgrade="LR-a"), _row("fabrik-review")]
    doc = _doc(tmp_path, rows, [_refusal("LR-a", agent="infra"), _refusal("LR-b", agent="infra")])
    assert doc["agents"]["infra"] == {"starts": 2, "refused": 2, "downgraded": 1}


def test_lane_a_task_with_an_exact_spec_infers_nothing_more(tmp_path: Path) -> None:
    """T06-O3: once a spec row carries the task's id, the task claims no second, id-less spec."""
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", surface="a", from_downgrade="LR-a"),
        _row("fabrik-spec", ts=T0, state="handoff", surface="b"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
    ]
    assert _doc(tmp_path, rows, [])["task_to_spec"]["downgraded_spec"] == 1


# ── closing pass (T06-O9, O11, O13) ──


def test_lane_a_negative_wall_is_untimed_not_a_median_value(tmp_path: Path) -> None:
    """T06-O11: a negative `wall_s` is no duration — it leaves the median and is disclosed."""
    rows = [
        _row("fabrik-task", wall=600),
        _row("fabrik-task", wall=1200),
        _row("fabrik-task", wall=-6000),
    ]
    t = _doc(tmp_path, rows, [])["task"]
    assert (t["median_min"], t["timed"], t["rows"]) == (15, 2, 3)


def test_lane_undated_feedback_rows_are_disclosed(tmp_path: Path) -> None:
    """T06-O13: a row with no numeric `ts` falls outside every window — counted, never silent."""
    rows = [_row("fabrik-task"), _row("fabrik-task", ts=None), _row("fabrik-task", ts="later")]
    doc = _doc(tmp_path, rows, [])
    assert (doc["coverage"]["feedback_rows"], doc["coverage"]["undated_rows"]) == (1, 2)
    head = _lane(tmp_path, rows, []).stdout.splitlines()[0]
    assert "1 feedback rows [+2 undated], 0 refusal rows" in head


# ── T08-D7 C-O2: the downgrade join is EXACT — an id-less handoff never joins a task ──


def test_c_o2_an_id_less_handoff_is_never_a_downgrade_and_the_task_is_unjoined(
    tmp_path: Path,
) -> None:
    rows = [
        _row("fabrik-spec", ts=T0, state="handoff", surface="a"),  # an ordinary handoff
        _row("fabrik-spec", ts=T0, state="handoff", surface="b", from_downgrade="LR-b"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-a"),
        _row("fabrik-task", ts=T0 + 900, wall=300, from_downgrade="LR-b"),
    ]
    tts = _doc(tmp_path, rows, [])["task_to_spec"]
    assert (tts["spec"], tts["downgraded_spec"], tts["unjoined_downgrades"]) == (2, 1, 1)
    text = _lane(tmp_path, rows, []).stdout
    assert "1 downgraded /fabrik-task run joins no /fabrik-spec handoff" in text, text
