"""Behavior-Contract tests for the structured close-out USAGE feedback (D-175, operator's 6th ask).

Every close (`done` / `blocked` / `handoff`) of a run started after the cutoff must carry the four
labelled fields — `confusion:` `waste:` `change:` `filed:` — so the feedback describes how the
COMMAND behaved (what confused, what cost tokens for nothing, the one edit that would have made
the run faster or more accurate, what was filed), not only what was mailed. The close refuses
anything else, appends a row to the fleet-wide ledger with the auto-captured wall-clock and
round count, and prints the exact `FEEDBACK:` line to paste into the FINAL OUTPUT block.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_run.py"
STRUCTURED = (
    "confusion: step 3's 'arm' verb read as a dispatch · waste: two gate re-runs on an "
    "unchanged tree · change: name the rubric command in step 2 · filed: none — surfaces "
    "exercised: the rubric, the round ledger"
)


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state" / "command-runs"
    d.mkdir(parents=True)
    return d


def _cr(run_dir: Path, *args: str, sid: str = "s1") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "COMMAND_RUN_DIR": str(run_dir), "CLAUDE_SESSION_ID": sid}
    env.pop("CLAUDE_AGENT", None)
    # never read the developer's real marker or transcript from a test (review 2026-09-07) —
    # force-assigned, so an ambient export of either seam cannot leak in (pass-14 seat A)
    env["COMMAND_RUN_ACCOUNT_FILE"] = str(run_dir / "no-marker")
    env["COMMAND_RUN_TRANSCRIPT"] = str(run_dir / "no-transcript.jsonl")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=30, env=env
    )


def _start(run_dir: Path) -> None:
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "3",
        "--terminal",
        "found:0 no-op round",
    )
    assert r.returncode == 0, r.stdout + r.stderr


def _ledger(run_dir: Path) -> list[dict]:
    p = run_dir.parent / "command-feedback.jsonl"
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_a_close_without_the_four_usage_fields_is_refused(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "round 3 found: 0",
        "--feedback",
        "none — surfaces exercised: the rubric, the round ledger",
    )
    assert r.returncode == 1, r.stdout
    assert "confusion:" in r.stdout and "waste:" in r.stdout and "change:" in r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "running"  # the refusal leaves the record where the Stop hook sees it
    assert _ledger(run_dir) == []


def test_a_structured_close_lands_a_ledger_row_with_the_auto_captured_metrics(
    run_dir: Path,
) -> None:
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "4", "--classes-swept", "a,b", "--classes-new", "")
    _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a,b", "--classes-new", "")
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "round 2 found: 0",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    rows = _ledger(run_dir)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["command"] == "fabrik-probe" and row["state"] == "done" and row["sid"] == "s1"
    assert row["rounds"] == 2 and row["findings"] == [4, 0]
    assert isinstance(row["wall_s"], (int, float)) and row["wall_s"] >= 0
    assert row["confusion"].startswith("step 3's")
    assert row["waste"].startswith("two gate re-runs")
    assert row["change"].startswith("name the rubric")
    assert row["filed"].startswith("none — surfaces exercised")
    # the printed line is the FINAL OUTPUT block's 7th line, ready to paste
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("FEEDBACK:"))
    assert "/fabrik-probe" in line and "rounds 2" in line and "change: name the rubric" in line
    # the filing verdict is still classified from the `filed:` field alone
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["feedback"] == "none", rec["feedback"]


def test_a_filed_field_still_classifies_as_filed(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "blocked",
        "--command",
        "fabrik-probe",
        "--reason",
        "missing infra - searched: a - missing: b",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: 01M11VS2ZE to intel — dead modules",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["feedback"] == "filed" and rec["feedback_to"] == ["intel"]
    assert _ledger(run_dir)[0]["state"] == "blocked"


def test_an_empty_field_value_is_refused_like_a_missing_one(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: · waste: none · change: none · filed: none — surfaces exercised: x",
    )
    assert r.returncode == 1, r.stdout
    assert "missing, empty or duplicated: confusion:" in r.stdout, r.stdout


def test_a_bare_none_in_the_filed_field_is_still_refused(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: none",
    )
    assert r.returncode == 1, r.stdout
    assert "surfaces" in r.stdout.lower()


def test_a_label_named_inside_a_value_does_not_split_the_field(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: rename the 'waste:' label to 'burn:' · "
        "filed: mailed the cost:5 defect 01M1XYZ to infra",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["change"] == "rename the 'waste:' label to 'burn:'", row
    assert row["filed"] == "mailed the cost:5 defect 01M1XYZ to infra", row
    assert row["cost"] == "", row


def test_a_duplicated_label_is_refused_not_last_wins(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: 01M1 to infra · filed: none",
    )
    assert r.returncode == 1, r.stdout
    assert "filed (duplicate):" in r.stdout, r.stdout
    assert _ledger(run_dir) == []


def test_a_grandfathered_close_writes_no_ledger_row_even_when_its_text_carries_a_label(
    run_dir: Path,
) -> None:
    _start(run_dir)
    f = run_dir / "s1.json"
    rec = json.loads(f.read_text(encoding="utf-8"))
    rec["started_at"] = (
        "2026-08-30T00:00:00+00:00"  # after the presence cutoff, before the usage one
    )
    f.write_text(json.dumps(rec), encoding="utf-8")
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "filed: 01M1 to infra — the old free-text shape, one label by accident",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir) == []
    assert not any(ln.startswith("FEEDBACK:") for ln in r.stdout.splitlines())


def test_the_row_carries_agent_surface_account_and_a_numeric_cost(
    run_dir: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "active-account"
    marker.write_text("ob-ocoron-com-s-organization\n", encoding="utf-8")
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "CLAUDE_AGENT": "infra",
        "COMMAND_RUN_ACCOUNT_FILE": str(marker),
    }
    args = [
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "1",
        "--terminal",
        "t",
        "--surface",
        "docs/development/plans/2026-09-07-plan-1-x.md",
    ]
    r = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=30, env=env
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED + " · cost: pool $0.0125",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["agent"] == "infra"
    assert row["surface"] == "docs/development/plans/2026-09-07-plan-1-x.md"
    assert row["account"] == "ob-ocoron-com-s-organization"
    assert row["cost"] == "pool $0.0125" and row["cost_usd"] == 0.0125


def test_missing_agent_surface_account_and_cost_record_as_empty_not_absent(run_dir: Path) -> None:
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "COMMAND_RUN_ACCOUNT_FILE": str(run_dir / "no-such-marker"),
    }
    env.pop("CLAUDE_AGENT", None)
    r = subprocess.run(  # no --surface, no CLAUDE_AGENT, no account marker
        [
            sys.executable,
            str(SCRIPT),
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["agent"] == "" and row["surface"] == "" and row["account"] == ""
    assert row["cost"] == "" and row["cost_usd"] is None


def test_the_close_can_name_the_surface_a_start_omitted(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--surface",
        "git diff a1b2c3d..HEAD",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir)[0]["surface"] == "git diff a1b2c3d..HEAD"


def test_cost_usd_parses_marked_or_whole_numbers_and_never_prose() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("pool $0.0125") == 0.0125
    assert _cost_usd("0.03") == 0.03
    assert _cost_usd("pool 0.0017 USD") == 0.0017
    assert _cost_usd("$1,234.50") == 1234.5
    assert _cost_usd("about 0.01 usd across three units") == 0.01
    assert _cost_usd("2 hold-era commits, 1 orphaned native pass") is None  # prose, not dollars
    assert _cost_usd("") is None


def test_a_refused_close_does_not_persist_its_late_surface(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-other",
        "--evidence",
        "x",
        "--surface",
        "late-surface",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 1, r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["surface"] == "" and rec["state"] == "running"
    # a second, LATER refusal path — the usage-field check — must not persist it either
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--surface",
        "late-surface",
        "--feedback",
        "confusion: none · waste: none",
    )
    assert r.returncode == 1, r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["surface"] == "" and rec["state"] == "running"
    assert _ledger(run_dir) == []


def _transcript_line(
    ts_epoch: float, tin: int, tout: int, cr: int, cc: int, model: str = "claude-x", mid: str = ""
) -> str:
    import datetime as dt

    ts = dt.datetime.fromtimestamp(ts_epoch, tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": ts,
            "message": {
                "id": mid or f"msg_{ts_epoch}",
                "model": model,
                "usage": {
                    "input_tokens": tin,
                    "output_tokens": tout,
                    "cache_read_input_tokens": cr,
                    "cache_creation_input_tokens": cc,
                },
            },
        }
    )


def test_the_row_sums_the_transcripts_token_usage_inside_the_run_window(
    run_dir: Path, tmp_path: Path
) -> None:
    tr = tmp_path / "s1.jsonl"
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "COMMAND_RUN_TRANSCRIPT": str(tr),
    }
    env.pop("CLAUDE_AGENT", None)
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # anchor the fixture on the RUN's own clock, not the test's — a >3 s interpreter start
    # between the two flipped the assertions (review 2026-09-07, native seat)
    now = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))["started_epoch"]
    tr.write_text(
        "\n".join(
            [
                _transcript_line(now - 3600, 1000, 1000, 1000, 1000),  # an hour before: excluded
                json.dumps({"type": "user", "timestamp": "2026-01-01T00:00:00.000Z"}),  # no usage
                _transcript_line(now + 1, 10, 200, 5000, 700, model="claude-a", mid="m1"),
                # the same message again — one line per content block, usage repeated: NOT summed
                _transcript_line(now + 1, 10, 200, 5000, 700, model="claude-a", mid="m1"),
                "{not json",
                _transcript_line(now + 2, 5, 100, 3000, 300, model="claude-b", mid="m2"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["tok_in"] == 15 and row["tok_out"] == 300
    assert row["tok_cache_read"] == 8000 and row["tok_cache_create"] == 1000
    assert row["tok_msgs"] == 2 and row["models"] == ["claude-a", "claude-b"]
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("FEEDBACK:"))
    assert "tokens" in line and "cached" in line, line


def test_a_missing_transcript_records_null_tokens_not_zero(run_dir: Path) -> None:
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "COMMAND_RUN_TRANSCRIPT": str(run_dir / "no-such-transcript.jsonl"),
    }
    env.pop("CLAUDE_AGENT", None)
    for args in (
        ["start", "--command", "fabrik-probe", "--phases", "1", "--terminal", "t"],
        ["done", "--command", "fabrik-probe", "--evidence", "x", "--feedback", STRUCTURED],
    ):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["tok_in"] is None and row["tok_out"] is None and row["tok_msgs"] == 0
    assert row["models"] == []


def test_transcript_path_maps_the_cwd_to_claude_codes_project_slug(
    tmp_path: Path, monkeypatch
) -> None:
    """Every non-alphanumeric byte of the ABSOLUTE cwd becomes '-' (measured against the live
    ~/.claude/projects dirs: /opt/fabrik/.tmp/rivals/.neutral-cwd -> -opt-fabrik--tmp-rivals--neutral-cwd)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _transcript_path  # noqa: PLC0415

    monkeypatch.delenv("COMMAND_RUN_TRANSCRIPT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    d = tmp_path / ".claude" / "projects" / "-opt-my-repo--tmp-x-y"
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text("", encoding="utf-8")
    assert _transcript_path("s1", "/opt/my_repo/.tmp/x.y") == d / "s1.jsonl"
    assert _transcript_path("s2", "/opt/my_repo/.tmp/x.y") is None  # no transcript ⇒ None
    assert _transcript_path("", "/opt/my_repo") is None


def _usage_line(ts_epoch: float, mid: str, tout: int = 10) -> str:
    return _transcript_line(ts_epoch, 1, tout, 100, 10, mid=mid)


def test_a_stale_appended_block_never_truncates_the_window_scan(
    tmp_path: Path, monkeypatch
) -> None:
    """Claude Code re-emits earlier messages with their ORIGINAL timestamps on a compaction
    (measured on the live hub transcript: a 1340-line block lagging 23 h in the last 64 MiB).
    A run that spans a compaction has in-window messages on BOTH sides of that block; a scan
    that stops after N consecutive older lines loses everything before the block."""
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _sum_transcript_usage  # noqa: PLC0415

    now = time.time()
    start = now - 600
    lines = [_usage_line(start + 10, "before-compaction", tout=100)]
    lines += [_usage_line(start - 86400 - i, f"stale-{i}") for i in range(2000)]  # a day old
    lines += [_usage_line(start + 500, "after-compaction", tout=7)]
    tr = tmp_path / "t.jsonl"
    tr.write_text("\n".join(lines) + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_msgs"] == 2 and got["tok_out"] == 107, got
    assert got["tok_partial"] is False


def test_hitting_the_byte_cap_inside_the_window_marks_the_row_partial(
    tmp_path: Path, monkeypatch
) -> None:
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    import command_run as cr  # noqa: PLC0415

    now = time.time()
    start = now - 600
    lines = [_usage_line(start + i, f"m{i}") for i in range(200)]  # all inside the window
    tr = tmp_path / "t.jsonl"
    tr.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(cr, "_TRANSCRIPT_MAX_BYTES", 2048)  # far smaller than the file
    got = cr._sum_transcript_usage(tr, start, now)
    assert 0 < got["tok_msgs"] < 200 and got["tok_partial"] is True, got
    monkeypatch.setattr(cr, "_TRANSCRIPT_MAX_BYTES", 1 << 30)
    full = cr._sum_transcript_usage(tr, start, now)
    assert full["tok_msgs"] == 200 and full["tok_partial"] is False


def test_cost_usd_refuses_malformed_thousands_groups_instead_of_guessing() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("$1,234,567.89") == 1234567.89
    assert _cost_usd("$12,34") is None  # not a thousands group — a wrong 12.0 would be summed
    assert _cost_usd("$1,23,456") is None
    assert _cost_usd("$1234,567") is None
    assert _cost_usd("we spent about $1,23 today") is None


def test_late_surface_lands_on_blocked_and_handoff_closes(run_dir: Path, tmp_path: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "blocked",
        "--command",
        "fabrik-probe",
        "--reason",
        "missing infra - searched: a - missing: b",
        "--surface",
        "spec-x",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir)[0]["surface"] == "spec-x"
    _start(run_dir)
    art = tmp_path / "resume.md"
    art.write_text("## RESUME\n- row\n", encoding="utf-8")
    r = _cr(
        run_dir,
        "handoff",
        "--command",
        "fabrik-probe",
        "--resume",
        str(art),
        "--reason",
        "rows open",
        "--surface",
        "spec-y",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir)[-1]["surface"] == "spec-y"


def test_tokens_clause_handles_a_zero_context_and_a_null_row() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _tokens_clause  # noqa: PLC0415

    assert _tokens_clause({}) == ""
    assert _tokens_clause({"tok_in": None}) == ""
    z = {"tok_in": 0, "tok_out": 5, "tok_cache_read": 0, "tok_cache_create": 0}
    assert _tokens_clause(z) == "tokens 0 input / 5 output"  # no division, no percent


def test_a_message_whose_lines_disagree_keeps_the_largest_usage_whatever_the_order(
    tmp_path: Path,
) -> None:
    """Measured on the live hub transcript (2026-09-07): 3 of 2,857 message ids carry one line
    with ALL-ZERO usage beside the real one. First-seen-wins depends on write order; the
    per-message maximum does not."""
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _sum_transcript_usage  # noqa: PLC0415

    now = time.time()
    start = now - 600
    for order in ("zero-last", "zero-first"):
        real = _transcript_line(start + 10, 56, 4690, 991877, 7327, mid="m1")
        zero = _transcript_line(start + 11, 0, 0, 0, 0, mid="m1")
        lines = [real, zero] if order == "zero-last" else [zero, real]
        tr = tmp_path / f"{order}.jsonl"
        tr.write_text("\n".join(lines) + "\n", encoding="utf-8")
        got = _sum_transcript_usage(tr, start, now)
        assert got["tok_msgs"] == 1, (order, got)
        assert (got["tok_in"], got["tok_out"], got["tok_cache_read"]) == (56, 4690, 991877), (
            order,
            got,
        )


def test_a_usd_marked_number_needs_a_fraction_so_prose_years_are_not_dollars() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("budget for 2024 usd fiscal year") is None  # a year, not a cost
    assert _cost_usd("1.0 usd across three units") == 1.0
    assert _cost_usd("$2024") == 2024.0  # the $ marker is explicit — accepted as written


# ── /fabrik-review 2026-09-07, native Opus seat: eight regression guards ────────────────────


def test_a_non_finite_usage_value_never_wedges_the_close(run_dir: Path, tmp_path: Path) -> None:
    """`json.loads` accepts the literal Infinity; int(inf) raises OverflowError, which the old
    except tuple let escape — main() then returned rc 0 with the record still `running`."""

    tr = tmp_path / "s1.jsonl"
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "COMMAND_RUN_TRANSCRIPT": str(tr),
    }
    env.pop("CLAUDE_AGENT", None)
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    started = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))["started_epoch"]
    good = _transcript_line(started + 1, 10, 20, 30, 40, mid="ok")
    bad = _transcript_line(started + 2, 1, 1, 1, 1, mid="inf").replace(
        '"input_tokens": 1', '"input_tokens": Infinity'
    )
    tr.write_text(good + "\n" + bad + "\n", encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0 and "run record closed" in r.stdout, r.stdout + r.stderr
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "done"
    row = _ledger(run_dir)[0]
    assert row["tok_msgs"] == 2 and row["tok_in"] == 10 and row["tok_out"] == 21, row  # inf → 0


def test_cost_usd_sums_every_marked_amount_or_refuses_an_ambiguous_mix() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("$0 pool + $1.40 ai-consult") == 1.4
    assert _cost_usd("pool $0.12 + $0.30 ai-consult") == 0.42
    assert _cost_usd("3 pool workers, $0.44 total") == 0.44


def test_the_late_surface_override_sits_below_every_refusal_in_close(run_dir: Path) -> None:
    """In-process: a refused close must leave the in-memory record's surface untouched — the
    CLI-level test could not see this (a refusal never saves), so it was vacuous under mutation."""
    import argparse

    sys.path.insert(0, str(ROOT / "scripts"))
    import command_run as cr  # noqa: PLC0415

    _start(run_dir)
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    args = argparse.Namespace(
        cmd="done",
        command="fabrik-other",
        evidence="x",
        feedback=STRUCTURED,
        surface="late",
        session=None,
        adopt_sid=False,
    )
    rc = cr._close("s1", rec, args, {})
    assert rc == 1 and rec.get("surface", "") == "", rec.get("surface")


def test_the_feedback_line_labels_the_input_sum_honestly_and_scales_to_millions() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _tokens_clause  # noqa: PLC0415

    tok = {
        "tok_in": 4614,
        "tok_out": 104676,
        "tok_cache_read": 18660086,
        "tok_cache_create": 149051,
    }
    line = _tokens_clause(tok)
    assert line.startswith("tokens 18.8M input / 104.7k output"), line
    assert "context" not in line and "(99% cached)" in line, line


def test_a_grandfathered_close_still_records_a_late_surface_on_the_record(run_dir: Path) -> None:
    _start(run_dir)
    f = run_dir / "s1.json"
    rec = json.loads(f.read_text(encoding="utf-8"))
    rec["started_at"] = "2026-09-01T00:00:00+00:00"  # pre-cutoff: no ledger row, old grammar
    f.write_text(json.dumps(rec), encoding="utf-8")
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--surface",
        "late-g",
        "--feedback",
        "none — surfaces exercised: x",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(f.read_text(encoding="utf-8"))["surface"] == "late-g"
    assert _ledger(run_dir) == []


def test_a_newline_free_tail_is_abandoned_not_accumulated(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import command_run as cr  # noqa: PLC0415

    f = tmp_path / "garbage.jsonl"
    f.write_bytes(
        b"a\nb\n" + b"x" * (cr._TRANSCRIPT_MAX_LINE + (2 << 20))
    )  # a 'line' longer than any record
    got = list(cr._iter_lines_backwards(f, 64 << 20))
    assert got == [None], (
        got
    )  # bailed: the sentinel says the read was cut short, nothing torn yielded
    ok = tmp_path / "ok.jsonl"
    ok.write_bytes(b"a\nb\nc\n")
    assert list(cr._iter_lines_backwards(ok, 64 << 20)) == [b"", b"c", b"b", b"a"]


def test_the_ledger_row_is_appended_with_one_write_and_fields_are_capped(run_dir: Path) -> None:
    _start(run_dir)
    huge = (
        "confusion: "
        + ("x" * 6000)
        + " · waste: none · change: none · filed: none — surfaces exercised: y"
    )
    r = _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "x", "--feedback", huge)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert len(row["confusion"]) <= 2000 and row["confusion"].endswith("…")


# ── /fabrik-review pass 2 (scoped on the pass-1 fixes) ──────────────────────────────────


def test_a_naive_timestamp_is_not_dropped_by_the_prefilter(tmp_path: Path) -> None:
    import datetime as dt
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _sum_transcript_usage  # noqa: PLC0415

    now = time.time()
    start = now - 600
    naive = dt.datetime.fromtimestamp(start + 5).strftime("%Y-%m-%dT%H:%M:%S.000")  # no Z, local
    line = _transcript_line(start + 5, 7, 8, 9, 10, mid="n1").replace(
        dt.datetime.fromtimestamp(start + 5, tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"), naive
    )
    assert naive in line and "Z" not in line.split('"timestamp": "')[1][:24]
    tr = tmp_path / "t.jsonl"
    tr.write_text(line + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_msgs"] == 1 and got["tok_in"] == 7, got


def test_a_capped_read_that_saw_no_stamped_line_is_partial(tmp_path: Path, monkeypatch) -> None:
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    import command_run as cr  # noqa: PLC0415

    tr = tmp_path / "t.jsonl"
    tr.write_text("\n".join('{"type": "x"}' for _ in range(500)) + "\n", encoding="utf-8")
    monkeypatch.setattr(cr, "_TRANSCRIPT_MAX_BYTES", 256)
    got = cr._sum_transcript_usage(tr, time.time() - 60, time.time())
    assert got["tok_msgs"] == 0 and got["tok_partial"] is True, got


def test_the_ledger_append_loops_over_a_short_write(run_dir: Path, monkeypatch) -> None:
    """os.write may return fewer bytes than given; a row must never be truncated by it."""
    import os as _os

    sys.path.insert(0, str(ROOT / "scripts"))
    import command_run as cr  # noqa: PLC0415

    real = _os.write
    calls: list[int] = []

    def short(fd: int, data: bytes) -> int:
        n = min(len(data), 16)
        calls.append(n)
        return real(fd, data[:n])

    monkeypatch.setattr(cr.os, "write", short)
    target = run_dir.parent / "command-feedback.jsonl"
    cr._append_ledger_row(target, {"command": "fabrik-probe", "x": "y" * 100})
    rows = [json.loads(ln) for ln in target.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows == [{"command": "fabrik-probe", "x": "y" * 100}] and len(calls) > 1


# ── /fabrik-review pass 3 (closing sweep raised two) ────────────────────────────────────


def test_a_dollar_amount_followed_by_usd_inside_prose_counts_once() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("$0.05 usd total") == 0.05  # both alternatives matched the same number
    assert _cost_usd("about $0.01 usd for the pool") == 0.01
    assert _cost_usd("$0.12 + 0.30 usd") == 0.42  # two distinct amounts still sum


def test_the_surface_is_capped_like_every_other_row_field(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--surface",
        "s" * 5000,
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert len(row["surface"]) <= 2000 and row["surface"].endswith("…")


def test_the_agent_dimension_is_the_start_time_one_never_the_close_time_env(run_dir: Path) -> None:
    """`account` and `surface` are resolved at start; `agent` fell back to the CLOSE process's
    CLAUDE_AGENT when the start had none — a window renamed mid-run mis-attributed the row."""
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "COMMAND_RUN_ACCOUNT_FILE": str(run_dir / "no-marker"),
        "COMMAND_RUN_TRANSCRIPT": str(run_dir / "no-transcript.jsonl"),
    }
    env.pop("CLAUDE_AGENT", None)
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    env["CLAUDE_AGENT"] = "fleet"
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir)[0]["agent"] == ""


def test_id_less_lines_count_once_each_with_or_without_a_line_uuid(tmp_path: Path) -> None:
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _sum_transcript_usage  # noqa: PLC0415

    now = time.time()
    start = now - 600
    base = _transcript_line(start + 5, 1, 2, 3, 4)
    no_id = base.replace('"id": ' + json.dumps(f"msg_{start + 5}") + ", ", "")
    assert '"id"' not in no_id
    with_uuid = no_id[:-1] + ', "uuid": "line-1"}'
    with_uuid2 = no_id[:-1] + ', "uuid": "line-2"}'
    tr = tmp_path / "t.jsonl"
    tr.write_text("\n".join([no_id, with_uuid, with_uuid2]) + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_msgs"] == 3 and got["tok_in"] == 3, (
        got
    )  # a line without message.id cannot be grouped


def test_the_whole_value_usd_form_needs_a_fraction_like_the_marked_form() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("2024 usd") is None and _cost_usd("3 usd") is None
    assert (
        _cost_usd("pool 0.0017 USD") == 0.0017 and _cost_usd("$3") == 3.0 and _cost_usd("5") == 5.0
    )


def test_an_explicit_zero_before_usd_is_a_zero_cost_not_absent() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("0 usd") == 0.0 and _cost_usd("0 usd from the pool") == 0.0
    assert _cost_usd("10 usd") is None  # still a bare integer — a count, not a cost


def test_a_negated_amount_is_refused_never_read_as_a_charge() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("-$1.50") is None and _cost_usd("-1.50 usd") is None
    assert _cost_usd("$5 - $2 refund") is None  # a subtraction is not a sum of charges
    assert _cost_usd("$0.12 + $0.30") == 0.42


def test_a_number_glued_to_a_letter_is_refused_and_bools_are_not_tokens(tmp_path: Path) -> None:
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd, _sum_transcript_usage  # noqa: PLC0415

    assert _cost_usd("$1e10") is None and _cost_usd("$5k") is None and _cost_usd("$5 k") == 5.0
    now = time.time()
    start = now - 600
    line = _transcript_line(start + 5, 7, 8, 9, 10, mid="b1").replace(
        '"input_tokens": 7', '"input_tokens": true'
    )
    tr = tmp_path / "t.jsonl"
    tr.write_text(line + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_msgs"] == 1 and got["tok_in"] == 0 and got["tok_out"] == 8, got


def test_a_tight_subtraction_is_refused_too() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd, _fmt_tokens  # noqa: PLC0415

    assert (
        _cost_usd("$5-$2") is None
        and _cost_usd("$5- $2 refund") is None
        and _cost_usd("$5 -$2") is None
    )
    assert (
        _cost_usd("$0.12 + $0.30") == 0.42 and _cost_usd("pool-$0.30") is None
    )  # a hyphen before $ is ambiguous
    assert (
        _fmt_tokens(999_999) == "1.0M"
        and _fmt_tokens(999_499) == "999.5k"
        and _fmt_tokens(999) == "999"
    )


def test_a_hyphenated_name_beside_a_real_amount_never_nulls_the_cost() -> None:
    """Pass-8's negation guard fired on ANY dash-digit (`glm-5`, `T-11`, `round-3`) and nulled the
    real amount beside it — the exact shape an agent writes next to a pool cost."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("$0.30 via glm-5 pool") == 0.3
    assert _cost_usd("pool $0.42 (opus-5 fallback)") == 0.42
    assert _cost_usd("$0.10 (T-11 fix) round-3") == 0.1
    assert _cost_usd("0.30 usd via glm-5") == 0.3
    # the negations still refuse
    assert (
        _cost_usd("$5-$2") is None
        and _cost_usd("-$1.50") is None
        and _cost_usd("-1.50 usd") is None
    )


def test_a_negated_thousands_amount_in_the_usd_form_is_refused_too() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("saved -1,234.50 usd on this run") is None
    assert _cost_usd("refund of -12,345.67 usd issued") is None
    assert _cost_usd("1,234.50 usd across the pool") == 1234.5  # the positive form still parses


def test_a_read_cut_inside_a_stale_block_is_partial(tmp_path: Path, monkeypatch) -> None:
    """A compaction block at the byte cap hides in-window lines BEYOND the cap: no criterion on
    the scanned lines can prove the window was covered, so any cut read is partial."""
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    import command_run as cr  # noqa: PLC0415

    now = time.time()
    start = now - 600
    lines = [_usage_line(start + 5, "early", tout=100)]  # in-window, at the head (beyond the cap)
    lines += [
        _usage_line(start - 86400 - i, f"stale-{i}") for i in range(200)
    ]  # a compaction block
    lines += [_usage_line(start + 500, "late", tout=7)]
    tr = tmp_path / "t.jsonl"
    tr.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(cr, "_TRANSCRIPT_MAX_BYTES", 12000)  # cuts inside the stale block
    got = cr._sum_transcript_usage(tr, start, now)
    assert got["tok_msgs"] == 1 and got["tok_partial"] is True, got
    monkeypatch.setattr(cr, "_TRANSCRIPT_MAX_BYTES", 1 << 30)
    full = cr._sum_transcript_usage(tr, start, now)
    assert full["tok_msgs"] == 2 and full["tok_partial"] is False


def test_punctuation_after_an_amount_does_not_drop_it() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("pool $0.30, $0.40 ai-consult") == 0.7  # a trailing comma is punctuation
    assert _cost_usd("$0.30.") == 0.3  # a full stop too
    assert (
        _cost_usd("$12,34") is None and _cost_usd("$1e10") is None
    )  # malformed groups and letters still refuse


def test_a_multi_digit_zero_before_usd_is_still_zero() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert (
        _cost_usd("00 usd") == 0.0
        and _cost_usd("pool 000 usd") == 0.0
        and _cost_usd("10 usd") is None
    )


def test_a_thousands_grouped_integer_before_usd_is_an_amount() -> None:
    """`2024 usd` is a year and `5 usd` a count, but `1,000 usd` cannot be either."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("1,000 usd") == 1000.0 and _cost_usd("pool 1,500 usd for the week") == 1500.0
    assert _cost_usd("2024 usd") is None and _cost_usd("500 usd") is None
    assert _cost_usd("-1,000 usd") is None  # a negated grouped integer refuses too


def test_a_unicode_minus_or_a_dash_glued_to_an_amount_negates_but_a_spaced_em_dash_is_prose() -> (
    None
):
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("−$1.50") is None  # U+2212 MINUS SIGN
    assert _cost_usd("–$5") is None and _cost_usd("—$5") is None and _cost_usd("‑$5") is None
    assert _cost_usd("−$1.50 refund, real cost $0.30") is None  # never 1.8
    assert (
        _cost_usd("pool $0.30 — three units") == 0.3
    )  # a spaced em dash is this corpus's separator
    assert _cost_usd("$0.12 – $0.30") is None  # a dash BETWEEN amounts is a subtraction either way


def test_an_out_of_grammar_agent_name_records_as_empty(monkeypatch) -> None:
    """The trailer grammar `[a-z0-9-]{1,32}`: anything else is not an agent name."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _agent_name  # noqa: PLC0415

    for bad in ("Infra", "in_fra", "a" * 33, "infra intel", ""):
        monkeypatch.setenv("CLAUDE_AGENT", bad)
        assert _agent_name() == "", bad
    monkeypatch.setenv("CLAUDE_AGENT", " intel-2 ")
    assert _agent_name() == "intel-2"


def test_a_hyphen_inside_a_versioned_name_before_usd_is_not_a_minus() -> None:
    """`opus-4.5 usd` beside a real amount: a hyphen preceded by a letter is part of a name."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("used opus-4.5 usd equivalent, real cost $0.30") == 0.3
    assert _cost_usd("$0.30 via sonnet-4.5 usd pool") == 0.3
    assert (
        _cost_usd("-1.50 usd") is None
        and _cost_usd("$5-$2") is None
        and _cost_usd("x -1.50 usd") is None
    )


def test_a_dash_glued_before_dollar_negates_and_a_torn_fraction_refuses() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("pool-$0.30") is None  # a dash glued before `$` stays a negation
    assert _cost_usd("$5 .99") is None and _cost_usd("pool $5 .25 total") is None  # never 5.0


def test_a_usage_with_no_numeric_field_is_not_a_message(tmp_path: Path) -> None:
    """A present-but-malformed usage (string numbers) must not count as a real zero-token message."""
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _sum_transcript_usage  # noqa: PLC0415

    now = time.time()
    start = now - 600
    good = _transcript_line(start + 5, 7, 8, 9, 10, mid="ok")
    bad = _transcript_line(start + 6, 1, 1, 1, 1, mid="str").replace(
        '"input_tokens": 1', '"input_tokens": "500"'
    )
    bad = (
        bad.replace('"output_tokens": 1', '"output_tokens": "5"')
        .replace('"cache_read_input_tokens": 1', '"cache_read_input_tokens": "0"')
        .replace('"cache_creation_input_tokens": 1', '"cache_creation_input_tokens": "0"')
    )
    tr = tmp_path / "t.jsonl"
    tr.write_text(good + "\n" + bad + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_msgs"] == 1 and got["tok_in"] == 7, got


def test_a_dash_between_a_usd_amount_and_another_amount_is_a_subtraction() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("5.00 usd – $2.00") is None and _cost_usd("5.00 usd – 2.00 usd") is None
    assert _cost_usd("pool 5.00 usd – 2.00 usd refund") is None
    assert _cost_usd("5.00 usd + 2.00 usd") == 7.0


# ── the cost field is a NUMBER at the close, never prose (review 2026-09-07, pass 17) ──────


def test_a_prose_cost_is_refused_at_the_close_and_a_plain_amount_is_accepted(run_dir: Path) -> None:
    """Sixteen review passes each found one more prose shape the cost parser mis-read; the
    class ends at the contract: `cost:` is a plain amount or the close refuses."""
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        STRUCTURED + " · cost: $0.30 via glm-5 pool",
    )
    assert r.returncode == 1 and "cost:" in r.stdout and "plain amount" in r.stdout, r.stdout
    assert json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))["state"] == "running"
    assert _ledger(run_dir) == []
    for ok, want in (
        ("pool $0.30", 0.3),
        ("0.0125", 0.0125),
        ("$1,234.50", 1234.5),
        ("0.0017 USD", 0.0017),
        ("$0", 0.0),
    ):
        _start(run_dir)
        r = _cr(
            run_dir,
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED + " · cost: " + ok,
        )
        assert r.returncode == 0, (ok, r.stdout + r.stderr)
        assert _ledger(run_dir)[-1]["cost_usd"] == want, (ok, _ledger(run_dir)[-1]["cost"])


def test_a_bare_integer_before_usd_is_refused_at_the_close_not_stored_as_null(
    run_dir: Path,
) -> None:
    """`10 usd` passed the strict shape but the parser (rightly) reads a bare integer before usd
    as ambiguous — the close must refuse rather than write `cost_usd: null` silently."""
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        STRUCTURED + " · cost: 10 usd",
    )
    assert r.returncode == 1 and "cost:" in r.stdout and "$10" in r.stdout, r.stdout
    assert _ledger(run_dir) == []
    for ok, want in (("$10", 10.0), ("10.00 usd", 10.0), ("1,000 usd", 1000.0), ("0 usd", 0.0)):
        _start(run_dir)
        r = _cr(
            run_dir,
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED + " · cost: " + ok,
        )
        assert r.returncode == 0, (ok, r.stdout + r.stderr)
        assert _ledger(run_dir)[-1]["cost_usd"] == want, (ok, _ledger(run_dir)[-1]["cost"])


def test_a_sentence_final_period_after_the_cost_does_not_refuse_the_close(run_dir: Path) -> None:
    """`cost:` is the last field; a line that ends a sentence ends in a period."""
    for text, want in (("$0.30.", 0.3), ("$10.", 10.0), ("pool 0.0125.", 0.0125)):
        _start(run_dir)
        r = _cr(
            run_dir,
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED + " · cost: " + text,
        )
        assert r.returncode == 0, (text, r.stdout + r.stderr)
        assert _ledger(run_dir)[-1]["cost_usd"] == want, (text, _ledger(run_dir)[-1]["cost"])
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        STRUCTURED + " · cost: 10 usd.",
    )
    assert r.returncode == 1  # the period does not launder a bare integer before usd


def test_a_lone_period_cost_is_refused_not_treated_as_absent(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        STRUCTURED + " · cost: .",
    )
    assert r.returncode == 1 and "cost:" in r.stdout, r.stdout
    assert _ledger(run_dir) == []


def test_an_amount_that_overflows_to_infinity_is_refused(run_dir: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    big = "1" + "0" * 320
    assert _cost_usd(big) is None and _cost_usd("$" + big) is None
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        STRUCTURED + " · cost: " + big,
    )
    assert r.returncode == 1 and _ledger(run_dir) == []


def _envelope(ts_iso: str, mid: str, tin: int, nested_ts: str | None) -> str:
    """A transcript line in Claude Code's REAL key order — `message` (and every tool_use input
    inside it) is serialised BEFORE the envelope's own `timestamp`."""
    content: list[dict] = [{"type": "text", "text": "ok"}]
    if nested_ts is not None:
        content.append(
            {"type": "tool_use", "id": "t1", "name": "log", "input": {"timestamp": nested_ts}}
        )
    return json.dumps(
        {
            "parentUuid": None,
            "message": {
                "model": "claude-x",
                "id": mid,
                "role": "assistant",
                "content": content,
                "usage": {
                    "input_tokens": tin,
                    "output_tokens": 1,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
            "type": "assistant",
            "uuid": "u-" + mid,
            "timestamp": ts_iso,
        }
    )


def test_a_timestamp_key_inside_a_tool_input_never_stands_in_for_the_envelopes(
    tmp_path: Path,
) -> None:
    """Review pass 25 (seat A): `_TS_RE.search` took the FIRST `"timestamp"` in the line, and a
    tool call whose input carries a `timestamp` argument is serialised before the envelope's
    stamp — a 23:00 message with a nested 10:30 stamp was billed to the 10:00–11:00 run, and a
    10:30 message with a nested 2020 stamp was dropped from it. Measured live on one hub
    transcript: 2,226 of 261,368 lines carry more than one `"timestamp"` key, 0 of them assistant
    lines — the class is a tool-call input, real but rare, so the fix parses only such lines."""
    import datetime as dt
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _line_epoch, _sum_transcript_usage  # noqa: PLC0415

    def iso(epoch: float) -> str:
        return dt.datetime.fromtimestamp(epoch, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    now = float(int(time.time()))  # whole seconds: the envelope stamp carries no fraction
    start, end = now - 3600, now - 1800  # the run's window
    inside, outside = start + 600, end + 7200  # 10 min in; 2 h after the close
    line_late = _envelope(iso(outside), "m-late", 99000, iso(inside))  # nested stamp INSIDE
    line_in = _envelope(iso(inside), "m-in", 2000, "2020-01-01T00:00:00Z")  # nested OUTSIDE
    line_plain = _envelope(iso(inside), "m-plain", 300, None)
    assert line_late.count('"timestamp"') == 2 and line_plain.count('"timestamp"') == 1
    assert _line_epoch(line_late.encode()) == outside
    assert _line_epoch(line_in.encode()) == inside
    tr = tmp_path / "t.jsonl"
    tr.write_text("\n".join([line_plain, line_in, line_late]) + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, end)
    assert got["tok_msgs"] == 2 and got["tok_in"] == 2300, got  # m-in + m-plain, never m-late
    torn = line_late.encode()[:-1]  # both stamps present but no parseable envelope: no epoch
    assert torn.count(b'"timestamp"') == 2 and _line_epoch(torn) is None


def test_an_envelope_stamp_of_another_shape_is_never_replaced_by_a_nested_one() -> None:
    """Pass 26 (seat A): with the envelope's `timestamp` present but not in the regex's shape (a
    number, a date-only string), the lone regex match was a NESTED stamp promoted to the
    envelope's. Any line with more than one `"timestamp"` key is parsed, and a top-level value
    the reader cannot read is no epoch. A line too deeply nested for the JSON parser has no
    epoch either — never a RecursionError out of the close."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _line_epoch  # noqa: PLC0415

    nested = {"type": "tool_use", "input": {"timestamp": "2020-01-01T00:00:00Z"}}
    for top in (1700000000, "2026-09-07", None, ["2026-09-07T12:00:00Z"]):
        raw = json.dumps(
            {"message": {"content": [nested]}, "type": "assistant", "timestamp": top}
        ).encode()
        assert raw.count(b'"timestamp"') == 2
        assert _line_epoch(raw) is None, top
    deep = (
        b'{"message":{"a":' + b"[" * 200_000 + b'{"timestamp":"2020-01-01T00:00:00Z"}'
        b"]" * 200_000 + b'},"type":"assistant","timestamp":"2026-09-07T12:00:00Z"}'
    )
    assert _line_epoch(deep) is None  # unparseable ⇒ no epoch, and no exception


def test_an_unpersisted_close_writes_no_ledger_row_and_never_claims_closed(
    run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pass 27 (seat B): the ledger row asserting `done` was appended BEFORE `save()` flipped the
    record, and a failed save still printed "run record closed" with rc 0 — the Stop hook kept
    blocking on `running`, and the retry appended a SECOND row. The row is written only after
    the record persisted; an unpersisted close says so, exits 1, and the retry writes one row.
    Pass 28 (seat A): the same close also printed a pasteable FEEDBACK line and flushed a
    `run_close` kaizen event — a close that did not happen emits neither."""
    events_dir = run_dir.parent / "events"
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(events_dir))

    def run_close_events() -> int:
        return sum(
            ln.count('"run_close"')
            for f in events_dir.glob("*.jsonl")
            for ln in f.read_text(encoding="utf-8").splitlines()
        )

    _start(run_dir)
    fb = "confusion: none · waste: none · change: none · filed: none — surfaces exercised: x"
    done = ("done", "--command", "fabrik-probe", "--evidence", "round 3 found: 0", "--feedback", fb)
    os.chmod(run_dir, 0o555)  # the record dir cannot take the .json.tmp save
    try:
        r = _cr(run_dir, *done)
    finally:
        os.chmod(run_dir, 0o755)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "NOT CLOSED" in r.stdout and "run record closed" not in r.stdout, r.stdout
    assert "FEEDBACK:" not in r.stdout and run_close_events() == 0, r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "running" and _ledger(run_dir) == []
    r = _cr(run_dir, *done)  # the retry, once the dir is writable again
    assert r.returncode == 0 and "run record closed" in r.stdout, r.stdout + r.stderr
    assert r.stdout.index("FEEDBACK:") < r.stdout.index("DONE /fabrik-probe")
    assert run_close_events() == 1  # exactly one close event for exactly one close
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "done"
    rows = _ledger(run_dir)
    assert len(rows) == 1 and rows[0]["state"] == "done" and rows[0]["command"] == "fabrik-probe"


def _seat_file(sub: Path, agent_id: str, msgs: list[tuple[float, str, int, int]]) -> Path:
    """A per-seat transcript in the LIVE shape (`<sid>/subagents/agent-<id>.jsonl`, read from a real
    one 2026-09-08): assistant lines with the parent's per-message usage; a message repeats one
    line per content block, so the same id appears more than once."""
    import datetime as dt

    sub.mkdir(parents=True, exist_ok=True)
    lines = []
    for ts_epoch, mid, tout, cr in msgs:
        ts = dt.datetime.fromtimestamp(ts_epoch, tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        lines.append(
            json.dumps(
                {
                    "agentId": agent_id,
                    "isSidechain": True,
                    "type": "assistant",
                    "timestamp": ts,
                    "message": {
                        "id": mid,
                        "model": "claude-sonnet-5",
                        "usage": {
                            "input_tokens": 2,
                            "output_tokens": tout,
                            "cache_read_input_tokens": cr,
                            "cache_creation_input_tokens": 0,
                        },
                    },
                }
            )
        )
    f = sub / f"agent-{agent_id}.jsonl"
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


def test_the_row_sums_the_seats_own_transcripts_never_the_parents_result_line(
    tmp_path: Path,
) -> None:
    """D-192/D-193: a seat's spend lives in `<sid>/subagents/agent-*.jsonl`. The parent's tool-result
    line is the seat's LAST turn only (251 of 251 measured), a background seat writes no usage there
    at all — an instrument keyed on it saw 0 of the 40 seats run that day and the one it saw 10x
    under. Per-message maximum inside each seat file, summed across seats; a seat with no in-window
    message is not a seat; no seat ⇒ null, never a real zero; the FEEDBACK clause prints the seats."""
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _sum_transcript_usage, _tokens_clause  # noqa: PLC0415

    now = time.time()
    start = now - 600
    tr = tmp_path / "sid.jsonl"
    tr.write_text(_usage_line(start + 10, "m1", tout=100) + "\n", encoding="utf-8")
    sub = tmp_path / "sid" / "subagents"
    # seat a: two messages, the first re-emitted (same id, same usage) — counts once
    _seat_file(
        sub,
        "a",
        [
            (start + 20, "s1", 6000, 70000),
            (start + 21, "s1", 6000, 70000),
            (start + 30, "s2", 500, 80000),
        ],
    )
    # seat b: one in-window message; seat old: every message before the window
    _seat_file(sub, "b", [(start + 40, "s3", 4000, 30000)])
    _seat_file(sub, "old", [(start - 3600, "s9", 9999, 9999)])
    # a parent-line result carrying the seat's LAST turn must NOT be counted on top
    tr.write_text(
        tr.read_text()
        + json.dumps(
            {
                "type": "user",
                "timestamp": "2026-09-08T10:00:00.000Z",
                "toolUseResult": {"agentId": "a", "usage": {"output_tokens": 500}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_msgs"] == 1 and got["tok_out"] == 100  # the orchestrator's sum is unchanged
    assert got["seats_seen"] == 2 and got["tok_seat_out"] == 6000 + 500 + 4000
    assert got["tok_seat_cache_read"] == 70000 + 80000 + 30000 and got["tok_seat_in"] == 6
    assert "seats 2: 180.0k input / 10.5k output" in _tokens_clause(got)
    # seats in the window while the orchestrator has NO message in it: the seat half still prints
    tr.write_text(_usage_line(start - 3600, "m0", tout=1) + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_in"] is None and got["seats_seen"] == 2
    assert _tokens_clause(got).startswith("tokens — · seats 2:")
    # one bad seat file (a pathologically nested line) must never null the whole row — the
    # orchestrator's totals and the other seats survive (round-4 finding); and the mtime prefilter
    # is real: a seat file last written before the window opened is never opened
    import datetime as dt
    import os

    bad = sub / "agent-bad.jsonl"
    ts = dt.datetime.fromtimestamp(start + 20, tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    bad.write_text(  # an in-window assistant line whose payload is pathologically nested
        '{"type": "assistant", "timestamp": "'
        + ts
        + '", "message": {"id": "sx", "usage": {}}, "junk": '
        + "[" * 200_000
        + "]" * 200_000
        + "}\n",
        encoding="utf-8",
    )
    tr.write_text(_usage_line(start + 10, "m1", tout=100) + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["tok_out"] == 100 and got["seats_seen"] == 2 and got["tok_seat_out"] == 10500
    assert (
        got["seats_skipped"] == 1
    )  # the bad file is COUNTED as skipped, never invisible (round 6)
    bad.unlink()
    # round 7: a seat that finished near the close with NO orchestrator message in the window is
    # not "still running" — the partial test is inconclusive there and stays False (0.0 as the
    # orchestrator's last message degraded it to the bare 30-second test)
    _seat_file(sub, "late", [(now - 5, "s7", 10, 10)])
    tr.write_text(_usage_line(start - 3600, "m0", tout=1) + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr, start, now)
    assert got["seats_seen"] == 3 and got["seats_partial"] is False
    # and a row whose EVERY seat file was skipped still prints the seat half — as a skip
    assert _tokens_clause(
        {"tok_in": 1, "tok_out": 1, "tok_cache_read": 0, "tok_cache_create": 0, "seats_skipped": 2}
    ).endswith(" · seats: 2 skipped (oversize/unreadable transcript)")
    assert _tokens_clause(dict(got, seats_skipped=1)).endswith(" · 1 skipped")
    # no orchestrator message AND every seat skipped: the skip still prints (round-8 finding —
    # the early return for "nothing to print" ran before the skip clause)
    assert _tokens_clause({"tok_in": None, "seats_skipped": 2}) == (
        "tokens — · seats: 2 skipped (oversize/unreadable transcript)"
    )
    assert _tokens_clause({"tok_in": None}) == ""
    (sub / "agent-late.jsonl").unlink()  # the assertions below count two seats
    # a broken symlink beside the good files must not null the directory listing (round 5)
    (sub / "agent-gone.jsonl").symlink_to(sub / "no-such-file.jsonl")
    got = _sum_transcript_usage(tr, start, now)
    assert got["seats_seen"] == 2 and got["tok_seat_out"] == 10500
    (sub / "agent-gone.jsonl").unlink()
    stale = _seat_file(sub, "stale", [(start + 50, "s7", 1, 1)])
    os.utime(stale, (start - 100, start - 100))
    got = _sum_transcript_usage(tr, start, now)
    assert got["seats_seen"] == 2  # in-window lines, but the file predates the window: not opened
    # seats_partial: a seat whose newest line is younger than the orchestrator's newest message
    # AND within the close's last seconds is still running; a seat the orchestrator spoke AFTER
    # has returned (round-6 finding: the bare 30-second test flagged every gather-then-close)
    for f in sub.glob("agent-*.jsonl"):
        f.unlink()
    _seat_file(sub, "late", [(now - 5, "s8", 1, 1)])
    tr.write_text(_usage_line(now - 50, "m5", tout=1) + "\n", encoding="utf-8")
    assert _sum_transcript_usage(tr, start, now)["seats_partial"] is True
    tr.write_text(_usage_line(now - 3, "m6", tout=1) + "\n", encoding="utf-8")
    assert _sum_transcript_usage(tr, start, now)["seats_partial"] is False
    # no seat directory: null, and the clause carries no seat fragment
    tr2 = tmp_path / "other.jsonl"
    tr2.write_text(_usage_line(start + 10, "m1", tout=100) + "\n", encoding="utf-8")
    got = _sum_transcript_usage(tr2, start, now)
    assert (
        got["seats_seen"] == 0
        and got["tok_seat_out"] is None
        and "seats" not in _tokens_clause(got)
    )


def test_a_bare_round_inherits_the_stamp_and_a_disagreeing_count_is_said_and_graded(
    run_dir: Path,
) -> None:
    """Round-7 Opus finding: `dispatch 3` + `dispatch 4` then a bare `round` declared 0 seats
    (argparse's default) and the close's `seats_declared` grader read that 0 — the tool had the
    true 7 in the stamp all along. The stamp is the default now; a typed count that disagrees is
    said on stderr and recorded as typed; `seats_declared` on the ledger row is graded here (the
    mutant `_declared = 0` survived every test before)."""
    import time

    # not a review-shaped command: `done` on those also demands a persisted report in the repo
    _cr(run_dir, "start", "--command", "fabrik-features", "--phases", "1", "--surface", "x")
    _cr(run_dir, "dispatch", "--seats", "3")
    _cr(run_dir, "dispatch", "--seats", "4")
    p = _cr(run_dir, "round", "--findings", "1", "--classes-new", "a")
    assert p.returncode == 0 and "disagrees" not in p.stderr
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["rounds"][-1]["seats"] == 7 and rec["dispatch"]["released"] is True
    _cr(run_dir, "dispatch", "--seats", "5")
    p = _cr(run_dir, "round", "--seats", "2", "--findings", "0", "--classes-swept", "a")
    # a PARTIAL close (round-11 Opus finding): two tickets stamped into one round, the first
    # to close releases only what closed — 3 seats stay reserved, the marker is not `released`
    assert "releasing 2 of the 5 seat(s) stamped this round — 3 stay reserved" in p.stderr
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["rounds"][-1]["seats"] == 2  # recorded as typed
    assert rec["dispatch"]["seats"] == 3 and rec["dispatch"]["released"] is False
    p = _cr(run_dir, "round", "--seats", "3", "--findings", "0", "--classes-swept", "a")
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["dispatch"]["seats"] == 0 and rec["dispatch"]["released"] is True  # the full close
    p = _cr(run_dir, "round", "--seats", "9", "--findings", "0", "--classes-swept", "a")
    assert "disagrees" not in p.stderr  # no stamp left to disagree with
    # typed MORE than stamped (round 12: the branch had no grader): said, released in full
    _cr(run_dir, "dispatch", "--seats", "5")
    p = _cr(run_dir, "round", "--seats", "8", "--findings", "0", "--classes-swept", "a")
    assert "round --seats 8 disagrees with the 5 seat(s) stamped" in p.stderr
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["dispatch"]["seats"] == 0 and rec["dispatch"]["released"] is True
    # a partial close keeps the ORIGINAL stamp's clock (round 12: re-dating renewed the window)
    _cr(run_dir, "dispatch", "--seats", "6")
    stamped_ts = json.loads(next(run_dir.glob("*.json")).read_text())["dispatch"]["ts"]
    time.sleep(0.05)
    _cr(run_dir, "round", "--seats", "2", "--findings", "0", "--classes-swept", "a")
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["dispatch"]["seats"] == 4 and rec["dispatch"]["ts"] == stamped_ts
    _cr(run_dir, "round", "--seats", "4", "--findings", "0", "--classes-swept", "a")
    # a deliberate `dispatch --seats 0` is a KNOWN zero (round 12)
    _cr(run_dir, "dispatch", "--seats", "0")
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["dispatch"]["seats"] == 0 and rec["dispatch"]["released"] is True
    # a negative typed count is refused like `dispatch`'s (round 10: it reached the ledger as -5)
    p = _cr(run_dir, "round", "--seats", "-1", "--findings", "0")
    assert p.returncode == 2 and "must be >= 0" in p.stderr
    # a deliberate `--seats 0` beside a live stamp is recorded as 0 (round 9: `or` conflated it)
    _cr(run_dir, "dispatch", "--seats", "4")
    p = _cr(run_dir, "round", "--seats", "0", "--findings", "0", "--classes-swept", "a")
    # round 11: a deliberate 0 beside a stamp is a PARTIAL close — nothing released, all 4 stay
    assert "releasing 0 of the 4 seat(s) stamped this round — 4 stay reserved" in p.stderr
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["rounds"][-1]["seats"] == 0
    p = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-features",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: none — surfaces exercised: x",
    )
    assert p.returncode == 0, p.stderr
    ledger = run_dir.parent / "command-feedback.jsonl"
    row = json.loads(ledger.read_text().splitlines()[-1])
    assert row["seats_declared"] == 35  # 7+2+3+9+8+2+4+0: the tripwire's ledger figure
    # a closed record is never mutated by `dispatch` either (round-8: the docstring claimed it,
    # no test proved it)
    p = _cr(run_dir, "dispatch", "--seats", "3")
    assert "already closed" in (p.stdout + p.stderr)
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["dispatch"]["seats"] == 0 and rec["dispatch"]["released"] is True


def test_a_round_with_no_stamp_names_the_seats_that_ran_unstamped(
    run_dir: Path, monkeypatch
) -> None:
    """Fleet's live datapoint (2026-09-08): an execute-plan closed with `seats_declared 0` against
    `seats_seen 12` — honest dispatches, never stamped, and nothing said so until the close. A
    `round` with no stamp that finds seat transcripts newer than the previous round/step says so
    on stderr; a stamped round, or one with nothing new, says nothing."""
    import time

    # `_cr` pins COMMAND_RUN_TRANSCRIPT to run_dir/no-transcript.jsonl: the seat dir follows it
    _cr(run_dir, "start", "--command", "fabrik-features", "--phases", "1", "--surface", "x")
    sub = run_dir / "no-transcript" / "subagents"
    time.sleep(1.1)  # the fixture's whole-second timestamps
    _seat_file(sub, "a", [(time.time(), "s1", 10, 10)])
    _seat_file(sub, "b", [(time.time(), "s2", 10, 10)])
    p = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a")
    assert "2 seat transcript(s) since the last round and NO `dispatch --seats` stamp" in p.stderr
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["rounds"][-1]["seats"] == 0
    # nothing new since that round: silent
    p = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a")
    assert "seat transcript(s) since" not in p.stderr
    # stamped: silent, the stamp is the figure
    time.sleep(1.1)  # the fixture's whole-second timestamps
    # an UNREADABLE seat transcript (a read error → "skipped") still counts: it ran, and only
    # its mtime can date it (round-13 Opus finding: the dict guard dropped it silently)
    if os.geteuid() != 0:
        _seat_file(sub, "x", [(time.time(), "sx", 10, 10)])
        (sub / "agent-x.jsonl").chmod(0)
        p = _cr(run_dir, "round", "--findings", "1")
        (sub / "agent-x.jsonl").chmod(0o644)
        assert (
            "1 seat transcript(s) since the last round and NO `dispatch --seats` stamp" in p.stderr
        )
    # the seat is dated from its TAIL only (round-13 finding: a full read of every seat under
    # the record lock was ~50 ms/MB): a new line buried at the HEAD under 70 KB of old lines is
    # not the seat's newest line, and the nudge stays silent
    time.sleep(1.1)  # the fixture writes whole-second stamps; clear the round's sub-second ts
    _tnow = time.time()
    buried = [(_tnow, "sy", 10, 10)] + [(_tnow - 9000, f"sy{i}", 10, 10) for i in range(600)]
    _seat_file(sub, "y", buried)
    assert (sub / "agent-y.jsonl").stat().st_size > 70 * 1024
    p = _cr(run_dir, "round", "--findings", "1")
    assert "seat transcript(s) since" not in p.stderr
    # a seat whose LAST line is a tool result larger than the tail still counts: the date is
    # the newest line of any type — the assistant line is 9000 s OLD, so an assistant-only
    # dater reads this seat as silent (round-14 Opus finding: the fresh assistant line masked it)
    import datetime as dt

    time.sleep(1.1)
    _seat_file(sub, "z", [(time.time() - 9000, "sz", 10, 10)])
    with (sub / "agent-z.jsonl").open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "type": "user",
                    "timestamp": dt.datetime.fromtimestamp(time.time(), tz=dt.UTC).strftime(
                        "%Y-%m-%dT%H:%M:%S.000Z"
                    ),
                    "message": {"content": [{"type": "tool_result", "content": "x" * 100_000}]},
                }
            )
            + "\n"
        )
    p = _cr(run_dir, "round", "--findings", "1")
    assert "1 seat transcript(s) since the last round and NO `dispatch --seats` stamp" in p.stderr
    # round-14 Opus findings, each its own round: (1) a TORN tail line (mid-write, no newline)
    # carrying a nested stale stamp on a LIVE seat is skipped — the complete line before it
    # dates the seat and the nudge fires; (2) a torn line carrying a FUTURE stamp on a 9000 s-old
    # seat is skipped too — silent; (3) an EMPTY seat file counts (only its mtime dates it);
    # (4) a last line larger than the 4 MB walk counts — "skipped", never None

    def _stamp(t):
        return dt.datetime.fromtimestamp(t, tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    time.sleep(1.1)
    _seat_file(sub, "t1", [(time.time(), "st1", 10, 10)])
    with (sub / "agent-t1.jsonl").open("a") as fh:
        fh.write('{"type":"user","message":{"input":{"timestamp":"2020-01-01T00:00:00.000Z"')
    p = _cr(run_dir, "round", "--findings", "1")
    assert "1 seat transcript(s) since the last round and NO `dispatch --seats` stamp" in p.stderr
    time.sleep(1.1)
    _seat_file(sub, "t2", [(time.time() - 9000, "st2", 10, 10)])
    with (sub / "agent-t2.jsonl").open("a") as fh:
        fh.write(
            '{"type":"assistant","timestamp":"2030-01-01T00:00:00.000Z","message":{"usage":{}}}'
        )
    p = _cr(run_dir, "round", "--findings", "1")
    assert "seat transcript(s) since" not in p.stderr
    time.sleep(1.1)
    (sub / "agent-t3.jsonl").write_bytes(b"")
    p = _cr(run_dir, "round", "--findings", "1")
    assert "1 seat transcript(s) since the last round and NO `dispatch --seats` stamp" in p.stderr
    time.sleep(1.1)
    _seat_file(sub, "t4", [(time.time(), "st4", 10, 10)])
    with (sub / "agent-t4.jsonl").open("a") as fh:
        fh.write(
            json.dumps({"type": "user", "timestamp": _stamp(time.time()), "big": "x" * (5 << 20)})
            + "\n"
        )
    p = _cr(run_dir, "round", "--findings", "1")
    assert "1 seat transcript(s) since the last round and NO `dispatch --seats` stamp" in p.stderr
    # round-15 Opus finding: a giant last line is DATABLE (its envelope stamp is at its head) —
    # a STAMPED seat of that shape, touched after its close, must not re-fire the nudge
    time.sleep(1.1)
    _seat_file(sub, "t5", [(time.time(), "st5", 10, 10)])
    with (sub / "agent-t5.jsonl").open("a") as fh:
        fh.write(
            json.dumps({"type": "user", "timestamp": _stamp(time.time()), "big": "x" * (5 << 20)})
            + "\n"
        )
    _cr(run_dir, "dispatch", "--seats", "1")
    p = _cr(run_dir, "round", "--seats", "1", "--findings", "0")
    assert "seat transcript(s) since" not in p.stderr
    time.sleep(1.1)
    (sub / "agent-t5.jsonl").touch()
    p = _cr(run_dir, "round", "--findings", "0")
    assert "seat transcript(s) since" not in p.stderr
    _seat_file(sub, "c", [(time.time(), "s3", 10, 10)])
    _cr(run_dir, "dispatch", "--seats", "1")
    p = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a")
    assert "seat transcript(s) since" not in p.stderr
    rec = json.loads(next(run_dir.glob("*.json")).read_text())
    assert rec["rounds"][-1]["seats"] == 1
    # a NESTED child's seats were the child's to stamp (fleet's caveat): after the child closes,
    # the parent's next round must not read them as an unstamped fan-out
    _cr(run_dir, "start", "--command", "fabrik-review-scoped", "--phases", "1", "--surface", "y")
    time.sleep(1.1)  # the fixture's whole-second timestamps
    _seat_file(sub, "d", [(time.time(), "s4", 10, 10)])
    _cr(run_dir, "dispatch", "--seats", "1")
    _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a")
    p = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-review-scoped",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: none — surfaces exercised: y",
    )
    assert p.returncode == 0, p.stderr
    p = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a")
    assert "seat transcript(s) since" not in p.stderr
    # round-12 Opus: a STAMPED seat still flushing after its close must not re-fire the nudge on
    # the next empty round — the count is by the seat's in-window last line, not the file mtime
    time.sleep(1.1)  # the fixture's whole-second timestamps
    for f in sub.glob("agent-*.jsonl"):
        if f.stem == "agent-t3":
            continue  # the EMPTY seat is undatable and dated by mtime by design; t4/t5 are datable
        f.touch()
    p = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a")
    assert "seat transcript(s) since" not in p.stderr
    # and a malformed timestamp on the record never voids the round (advisory, guarded)
    rp = next(run_dir.glob("*.json"))
    rec = json.loads(rp.read_text())
    rec["started_epoch"] = "2026-09-08T12:00:00Z"
    rp.write_text(json.dumps(rec))
    p = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a")
    assert p.returncode == 0 and "error, continuing" not in p.stderr
    assert len(json.loads(rp.read_text())["rounds"]) == len(rec["rounds"]) + 1
