"""T08 backfill — behavior tests (ticket: T08-backfill.md).

Every test isolates KAIZEN_STATE_DIR / KAIZEN_EVENTS_DIR / KAIZEN_TRANSCRIPTS_DIR via
the autouse fixture — nothing here ever touches the operator's real ~/.claude/state or
the real transcript corpus. The real backfill run (ticket Step 3) is a separate,
sanctioned operator-state write; these tests prove the machinery only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))

import kaizen_backfill as kb  # noqa: E402
import kaizen_collect_v2 as kc  # noqa: E402
import kaizen_outcomes as ko  # noqa: E402

DASH = kc.DASH


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing in this suite may read/write the operator's real state or corpus."""
    monkeypatch.setenv("KAIZEN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("KAIZEN_TRANSCRIPTS_DIR", str(tmp_path / "projects"))
    monkeypatch.delenv("KAIZEN_BACKFILL_SINCE", raising=False)
    (tmp_path / "events").mkdir()
    (tmp_path / "projects").mkdir()


def _tr(root: Path, project: str, rel: str, lines: list[str], mday: str) -> Path:
    """Write one synthetic transcript and pin its mtime to ``mday`` (midday UTC)."""
    p = root / project / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = dt.datetime.fromisoformat(f"{mday}T12:00:00+00:00").timestamp()
    os.utime(p, (t, t))
    return p


def _user(ts: str, text: str, sidechain: bool = False) -> str:
    row: dict[str, object] = {
        "type": "user",
        "timestamp": ts,
        "message": {"content": text},
    }
    if sidechain:
        row["isSidechain"] = True
    return json.dumps(row)


def _skill(ts: str, skill: str) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": ts,
            "message": {
                "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]
            },
        }
    )


def _rows(era: str | None = None) -> list[dict]:
    rows = kc.read_rows()
    if era is None:
        return rows
    return [r for r in rows if r.get("era", "event") == era]


# ── derivation: era mark, dashes, channels, fail-open lines ──────────────────────────


def test_backfill_marks_era_and_dashes_event_only_fields(tmp_path: Path) -> None:
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "aaaa1111.jsonl",
        [
            _user("2026-06-05T10:00:00Z", "<command-name>/fabrik-review</command-name> go"),
            _skill("2026-06-05T10:02:00Z", "fabrik-plan-review"),
        ],
        "2026-06-05",
    )
    summary = kb.run_backfill()
    assert summary["appended"] == 1
    (row,) = _rows("transcript")
    assert row["sid"] == "aaaa1111"
    assert row["era"] == "transcript"
    assert row["facts_version"] == kb.TRANSCRIPT_FACTS_VERSION  # S9: never kc.FACTS_VERSION
    assert row["day"] == "2026-06-05"
    assert row["project"] == "-opt-alpha"
    assert row["first_ts"] == "2026-06-05T10:00:00.000+00:00"
    assert row["last_ts"] == "2026-06-05T10:02:00.000+00:00"
    # Every event-only field is an explicit `—` — never a fabricated zero/empty.
    for field in ("events", "gate", "runs", "stop_causes", "death_classes"):
        assert row[field] == DASH, field
    assert row["concurrent"] is None
    assert "exposure.project" in row["concurrent_reason"]
    assert row["lines_total"] == 2
    assert row["lines_unclassified"] == 0


def test_nested_subagent_transcripts_are_walked(tmp_path: Path) -> None:
    # rglob reuse: 5,848 of 11,270 corpus files live at <proj>/<sess>/subagents/*.jsonl.
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "sess-1/subagents/agent-bbbb.jsonl",
        [_user("2026-06-06T09:00:00Z", "hello")],
        "2026-06-06",
    )
    assert kb.run_backfill()["appended"] == 1
    (row,) = _rows("transcript")
    assert row["sid"] == "agent-bbbb"
    assert row["project"] == "-opt-alpha"


def test_invocation_channels_are_structure_keyed(tmp_path: Path) -> None:
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "cccc3333.jsonl",
        [
            _user("2026-06-07T10:00:00Z", "<command-name>/fabrik-review</command-name>"),
            # A sidechain user row is a dispatched subagent's BRIEF, never a keystroke.
            _user(
                "2026-06-07T10:01:00Z",
                "<command-name>/fabrik-review</command-name>",
                sidechain=True,
            ),
            # A quoted '"skill":"x"' in prose must not count; only a tool_use block does.
            _user("2026-06-07T10:02:00Z", 'try "skill":"fabrik-spec" maybe'),
            _skill("2026-06-07T10:03:00Z", "fabrik-plan-review"),
        ],
        "2026-06-07",
    )
    kb.run_backfill()
    (row,) = _rows("transcript")
    assert row["invocations"] == {
        "typed": {"fabrik-review": 1},
        "skill": {"fabrik-plan-review": 1},
    }


def test_torn_alien_blank_lines_counted_with_reason_never_crash(tmp_path: Path) -> None:
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "dddd4444.jsonl",
        ['{"type":"user"', "[1,2,3]", "", _user("2026-06-08T10:00:00Z", "ok")],
        "2026-06-08",
    )
    kb.run_backfill()
    (row,) = _rows("transcript")
    assert row["lines_total"] == 4
    assert row["lines_unclassified"] == 3
    assert row["unclassified_reasons"] == {
        "unparseable-json": 1,
        "not-an-object": 1,
        "blank-line": 1,
    }


def test_memory_error_on_one_file_skips_it_never_kills_the_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Live failure 2026-08-20: a >100MB transcript raised MemoryError under the run's
    # hard cap at file ~4000/11264 and killed the whole pass. One pathological file
    # must ride the unreadable count, never abort the corpus walk.
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "huge.jsonl",
        [_user("2026-06-05T10:00:00Z", "x")],
        "2026-06-05",
    )
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "small.jsonl",
        [_user("2026-06-06T10:00:00Z", "y")],
        "2026-06-06",
    )
    real_loads = json.loads

    def exploding_loads(raw: str, *a: object, **kw: object) -> object:
        if '"x"' in raw:
            raise MemoryError
        return real_loads(raw, *a, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(kb.json, "loads", exploding_loads)
    summary = kb.run_backfill()
    assert summary["appended"] == 1
    assert summary["skipped_unreadable"] == 1
    assert [r["sid"] for r in _rows("transcript")] == ["small"]
    assert "memory" in capsys.readouterr().err.lower()


# ── idempotence + resumability (the store is the checkpoint) ─────────────────────────


def test_idempotent_rerun_store_byte_identical(tmp_path: Path) -> None:
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "aaaa1111.jsonl",
        [_user("2026-06-05T10:00:00Z", "x")],
        "2026-06-05",
    )
    first = kb.run_backfill()
    assert first["appended"] == 1
    before = kc.facts_path().read_bytes()
    second = kb.run_backfill()
    assert second["appended"] == 0
    assert second["skipped_known"] == 1
    assert kc.facts_path().read_bytes() == before


def test_resumable_appends_only_missing_sessions(tmp_path: Path) -> None:
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "aaaa1111.jsonl",
        [_user("2026-06-05T10:00:00Z", "x")],
        "2026-06-05",
    )
    kb.run_backfill()
    prefix = kc.facts_path().read_bytes()
    _tr(
        tmp_path / "projects",
        "-opt-beta",
        "bbbb2222.jsonl",
        [_user("2026-06-04T10:00:00Z", "y")],
        "2026-06-04",
    )
    summary = kb.run_backfill()
    assert summary["appended"] == 1
    after = kc.facts_path().read_bytes()
    assert after.startswith(prefix)  # append-only: nothing rewritten, only added
    assert {r["sid"] for r in _rows("transcript")} == {"aaaa1111", "bbbb2222"}


# ── bounds: KAIZEN_BACKFILL_SINCE + the event-era boundary ───────────────────────────


def test_since_bound_skips_older_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIZEN_BACKFILL_SINCE", "2026-06-01")
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "old-file.jsonl",
        [_user("2026-05-01T10:00:00Z", "old")],
        "2026-05-01",
    )
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "new-file.jsonl",
        [_user("2026-06-02T10:00:00Z", "new")],
        "2026-06-02",
    )
    summary = kb.run_backfill()
    assert summary["skipped_since"] == 1
    assert summary["appended"] == 1
    assert [r["sid"] for r in _rows("transcript")] == ["new-file"]


def test_invalid_since_falls_open_to_full_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("KAIZEN_BACKFILL_SINCE", "not-a-date")
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "aaaa1111.jsonl",
        [_user("2026-05-01T10:00:00Z", "x")],
        "2026-05-01",
    )
    summary = kb.run_backfill()
    assert summary["appended"] == 1  # the bound is ignored, never a silent exclusion
    assert "KAIZEN_BACKFILL_SINCE" in capsys.readouterr().err


def _event_file(tmp_path: Path, sid: str, mday: str) -> Path:
    ev = tmp_path / "events" / f"{sid}.jsonl"
    ev.write_text('{"schema":1}\n', encoding="utf-8")
    t = dt.datetime.fromisoformat(f"{mday}T12:00:00+00:00").timestamp()
    os.utime(ev, (t, t))
    return ev


def test_event_ownership_decides_never_mtime_alone(tmp_path: Path) -> None:
    # Binding law (acceptance round 1): a file is excluded ONLY on evidence of
    # event-era ownership — a pre-event transcript whose mtime got bumped past the
    # epoch (backup restore, rsync without -a, editor touch) must still derive.
    _event_file(tmp_path, "eeee1111", "2026-08-10")  # epoch hint = 2026-08-10
    # A sid with an event-era STORE row is owned too, whatever its transcript mtime.
    kc.append_facts([{"facts_version": kc.FACTS_VERSION, "sid": "ffff2222", "day": "2026-08-11"}])
    _tr(  # post-epoch mtime but NO ownership evidence → DERIVED (hint counted)
        tmp_path / "projects",
        "-opt-alpha",
        "gggg3333.jsonl",
        [_user("2026-08-12T10:00:00Z", "x")],
        "2026-08-12",
    )
    _tr(  # old mtime, but its sid has an event FILE → owned, skipped
        tmp_path / "projects",
        "-opt-alpha",
        "eeee1111.jsonl",
        [_user("2026-06-02T10:00:00Z", "x")],
        "2026-06-02",
    )
    _tr(  # old mtime, but its sid has an event-era STORE row → owned, skipped
        tmp_path / "projects",
        "-opt-alpha",
        "ffff2222.jsonl",
        [_user("2026-06-01T10:00:00Z", "x")],
        "2026-06-01",
    )
    summary = kb.run_backfill()
    assert summary["skipped_event_owned"] == 2
    assert summary["appended"] == 1
    assert summary["derived_post_epoch_mtime"] == 1
    assert [r["sid"] for r in _rows("transcript")] == ["gggg3333"]


def test_epoch_boundary_equal_mday_derives_with_hint_counter(tmp_path: Path) -> None:
    # The exact mday == epoch boundary: still ownership-decided; the >= hint fires.
    _event_file(tmp_path, "eeee1111", "2026-08-10")
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "hhhh4444.jsonl",
        [_user("2026-08-10T10:00:00Z", "x")],
        "2026-08-10",
    )
    summary = kb.run_backfill()
    assert summary["appended"] == 1
    assert summary["derived_post_epoch_mtime"] == 1
    assert [r["sid"] for r in _rows("transcript")] == ["hhhh4444"]


def test_overlong_line_bounded_counted_never_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A single pathological LINE must never materialize (under a cgroup cap that is a
    # SIGKILL, not a catchable MemoryError): bounded readline, drained, counted.
    monkeypatch.setattr(kb, "MAX_LINE_BYTES", 200)
    huge = (
        '{"type":"user","message":{"content":"<command-name>/fabrik-review</command-name>'
        + "A" * 400
        + '"}}'
    )
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "iiii5555.jsonl",
        [_user("2026-06-05T10:00:00Z", "ok"), huge, _user("2026-06-05T11:00:00Z", "ok2")],
        "2026-06-05",
    )
    summary = kb.run_backfill()
    assert summary["appended"] == 1  # the pass completes; the row still derives
    (row,) = _rows("transcript")
    assert row["lines_total"] == 3
    assert row["unclassified_reasons"] == {"line-too-long": 1}
    assert row["invocations"]["typed"] == {}  # the over-long line was never parsed
    assert row["first_ts"] == "2026-06-05T10:00:00.000+00:00"
    assert row["last_ts"] == "2026-06-05T11:00:00.000+00:00"


def test_symlink_alias_collapses_to_one_derivation(tmp_path: Path) -> None:
    target = _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "x.jsonl",
        [_user("2026-06-05T10:00:00Z", "x")],
        "2026-06-05",
    )
    beta = tmp_path / "projects" / "-opt-beta"
    beta.mkdir()
    (beta / "x.jsonl").symlink_to(target)
    summary = kb.run_backfill()
    assert summary["alias_duplicates"] == 1
    assert summary["duplicate_key_dropped"] == 0
    assert summary["appended"] == 1
    (row,) = _rows("transcript")
    assert row["project"] == "-opt-alpha"  # path-asc keeps the first real path


def test_distinct_duplicate_key_richer_wins_and_is_counted(tmp_path: Path) -> None:
    # Documented rule: richer wins by lines_total, path asc as tie-break; the loss
    # is COUNTED so it is visible, never silently arbitrary-by-sort-order.
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "y.jsonl",
        [_user("2026-06-05T10:00:00Z", "a")],
        "2026-06-05",
    )
    _tr(
        tmp_path / "projects",
        "-opt-beta",
        "y.jsonl",
        [
            _user("2026-06-05T10:00:00Z", "a"),
            _user("2026-06-05T10:01:00Z", "b"),
            _user("2026-06-05T10:02:00Z", "c"),
        ],
        "2026-06-05",
    )
    summary = kb.run_backfill()
    assert summary["duplicate_key_dropped"] == 1
    assert summary["appended"] == 1
    (row,) = _rows("transcript")
    assert row["project"] == "-opt-beta"
    assert row["lines_total"] == 3


def test_sid_becoming_event_owned_mid_walk_dropped_at_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # TOCTOU: the owned-sids snapshot ages during the walk; the append seam re-checks.
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "sneaky.jsonl",
        [_user("2026-06-05T10:00:00Z", "x")],
        "2026-06-05",
    )
    calls = {"n": 0}

    def fake_owned(state: Path, events: Path) -> set[str]:
        calls["n"] += 1
        return set() if calls["n"] == 1 else {"sneaky"}

    monkeypatch.setattr(kb, "event_owned_sids", fake_owned)
    summary = kb.run_backfill()
    assert summary["dropped_became_event_owned"] == 1
    assert summary["appended"] == 0
    assert _rows("transcript") == []
    assert "became event-owned" in capsys.readouterr().err


# ── the noise-floor report ───────────────────────────────────────────────────────────


def test_report_lists_every_registered_metric_in_both_eras(tmp_path: Path) -> None:
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "aaaa1111.jsonl",
        [_user("2026-06-05T10:00:00Z", "x")],
        "2026-06-05",
    )
    summary = kb.run_backfill()
    report = Path(summary["report"])
    assert report == kc.state_dir() / "noise-floor@v1.md"
    text = report.read_text(encoding="utf-8")
    reg = kc.registry()
    for mid, mdef in reg.items():
        rows = [ln for ln in text.splitlines() if ln.startswith(f"| {mid} |")]
        assert len(rows) == 2, mid  # one per era — value or reasoned `—`
        assert any("| event |" in ln for ln in rows), mid
        assert any("| transcript |" in ln for ln in rows), mid
        assert mdef["hash"] in text, mid  # the definition hash the floor was computed under


def test_report_event_weekly_mean_variance_from_series(tmp_path: Path) -> None:
    reg = kc.registry()
    mdef = reg["rules_compliance"]
    series = kc.series_path("rules_compliance", int(mdef["version"]))
    series.parent.mkdir(parents=True, exist_ok=True)
    days = [  # W33: (1+2)/(2+2)=0.75 · W34: 1/1=1.0 → mean 0.875, pvariance 0.015625
        ("2026-08-10", 1, 2),
        ("2026-08-11", 2, 2),
        ("2026-08-17", 1, 1),
    ]
    with open(series, "w", encoding="utf-8") as fh:
        for day, num, den in days:
            fh.write(
                json.dumps(
                    {
                        "day": day,
                        "metric": "rules_compliance",
                        "version": mdef["version"],
                        "def_hash": mdef["hash"],
                        "value": num / den,
                        "numerator": num,
                        "denominator": den,
                        "cell": "x",
                    }
                )
                + "\n"
            )
    text = kb.write_report().read_text(encoding="utf-8")
    (line,) = [
        ln
        for ln in text.splitlines()
        if ln.startswith("| rules_compliance |") and "| event |" in ln
    ]
    assert "| 0.875 |" in line
    assert "| 0.015625 |" in line
    assert "| 2 |" in line  # n = weeks


def _seed_series(mid: str, rows: list[dict]) -> None:
    mdef = kc.registry()[mid]
    path = kc.series_path(mid, int(mdef["version"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({"metric": mid, "def_hash": mdef["hash"], **row}) + "\n")


def test_distribution_valued_series_reports_dash_with_reason(tmp_path: Path) -> None:
    _seed_series(
        "gate_failure_taxonomy",
        [{"day": "2026-08-10", "value": {"check_x": 3}, "numerator": 3, "denominator": 5}],
    )
    text = kb.write_report().read_text(encoding="utf-8")
    (line,) = [
        ln
        for ln in text.splitlines()
        if ln.startswith("| gate_failure_taxonomy |") and "| event |" in ln
    ]
    assert f"| {DASH} | {DASH} | 0 |" in line  # never a scalar proxy for a distribution
    assert "- gate_failure_taxonomy (event): distribution-valued" in text


def test_no_denominator_fmean_fallback_and_n1_variance_zero(tmp_path: Path) -> None:
    # hole_count publishes numerator-only rows → weekly value is the fmean of daily
    # values; one week → POPULATION variance is exactly 0.0, pinned here not in prose.
    _seed_series(
        "hole_count",
        [
            {"day": "2026-08-10", "value": 2, "numerator": 2, "denominator": None},
            {"day": "2026-08-11", "value": 4, "numerator": 4, "denominator": None},
        ],
    )
    text = kb.write_report().read_text(encoding="utf-8")
    (line,) = [
        ln for ln in text.splitlines() if ln.startswith("| hole_count |") and "| event |" in ln
    ]
    assert "| event | 3 | 0 | 1 |" in line  # fmean(2,4)=3 · variance 0.0 · n=1


def test_report_transcript_era_reasons_present(tmp_path: Path) -> None:
    text = kb.write_report().read_text(encoding="utf-8")
    for mid in kc.registry():
        assert f"- {mid} (transcript):" in text, mid
        # An empty event era is a reasoned `—`, never a fabricated number.
        assert f"- {mid} (event):" in text, mid


# ── progress + CLI ───────────────────────────────────────────────────────────────────


def test_progress_line_every_n_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(kb, "PROGRESS_EVERY", 2)
    for i in range(3):
        _tr(
            tmp_path / "projects",
            "-opt-alpha",
            f"sess-{i}.jsonl",
            [_user("2026-06-05T10:00:00Z", "x")],
            "2026-06-05",
        )
    kb.run_backfill()
    assert "2/3" in capsys.readouterr().out


def test_report_cli_mode_writes_report(tmp_path: Path) -> None:
    assert kb.main(["--report"]) == 0
    assert (kc.state_dir() / "noise-floor@v1.md").is_file()


# ── review fix-wave: adjudicated findings, red-first ─────────────────────────────────


def test_report_covers_the_full_registry(tmp_path: Path) -> None:
    """M7: the noise-floor report unions T06's registry with the outcome tier — every
    registered metric appears, each with an event-era and a transcript-era row."""
    text = kb.render_report()
    full = ko.registry()
    assert len(full) == 16  # W6-1 added the death_occurrences/death_classes pair
    for mid in full:
        assert f"| {mid} |" in text, f"{mid} missing from the noise-floor report"


def test_empty_corpus_backfill_is_a_clean_noop(tmp_path: Path) -> None:
    """B2: an empty transcript corpus walks to a clean no-op — zero files, zero rows
    appended, the report still written, no crash."""
    summary = kb.run_backfill()
    assert summary["files"] == 0
    assert summary["appended"] == 0
    assert Path(str(summary["report"])).is_file()
    assert not kc.facts_path(kc.state_dir()).exists(), "nothing derived from nothing"


# ── fix-wave 3 (S9: transcript rows carry their own facts version, red-first) ────────


def test_event_schema_bump_does_not_rederive_transcripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S9: transcript derivation is version-independent of the EVENT-era row schema —
    a kc.FACTS_VERSION bump must NOT re-append the ~11k-row corpus. Both the row's
    facts_version and the skip key carry TRANSCRIPT_FACTS_VERSION instead."""
    _tr(
        tmp_path / "projects",
        "-opt-alpha",
        "aaaa1111.jsonl",
        [_user("2026-06-05T10:00:00Z", "hello")],
        "2026-06-05",
    )
    first = kb.run_backfill()
    assert first["appended"] == 1
    (row,) = _rows("transcript")
    assert row["facts_version"] == kb.TRANSCRIPT_FACTS_VERSION == 1

    monkeypatch.setattr(kc, "FACTS_VERSION", kc.FACTS_VERSION + 1)
    second = kb.run_backfill()
    assert second["appended"] == 0, "an event-schema bump must not re-derive transcripts"
    assert second["skipped_known"] == 1


# ── fix-wave 4 (W4-3: era-aware keys + era-field census, red-first) ──────────────────


def test_v1_event_row_never_masks_the_transcript_skip_key(tmp_path: Path) -> None:
    """W4-3: TRANSCRIPT_FACTS_VERSION (1) collides numerically with live v1 EVENT
    rows — the era-blind skip key read the event row's (sid, 1, day) as "already
    derived" and silently skipped the transcript. The key carries the era, so only
    a TRANSCRIPT-era row at the triple counts as known."""
    # A v1 EVENT-era store row for an unrelated sid at the same day the transcript
    # will key on — NOT event ownership for the transcript's sid, but under the
    # era-blind key its (sid, 1, day) triple would collide if sids matched; prove
    # the era split directly through known_fact_keys.
    kc.append_facts(
        [{"facts_version": 1, "sid": "cccc4444", "day": "2026-06-05", "lines_total": 1}]
    )
    keys = kc.known_fact_keys(kc.state_dir())
    assert ("cccc4444", 1, "2026-06-05", "event") in keys
    assert ("cccc4444", 1, "2026-06-05", "transcript") not in keys, (
        "an event-era row must not occupy the transcript era's key space"
    )
    # And the transcript row lands beside it — same (sid, version, day), new era.
    appended = kc.append_facts(
        [
            {
                "facts_version": kb.TRANSCRIPT_FACTS_VERSION,
                "era": "transcript",
                "sid": "cccc4444",
                "day": "2026-06-05",
                "events": DASH,
                "lines_total": 5,
            }
        ]
    )
    assert appended == 1, "a v1 event row must never mask the transcript derivation"


def test_census_counts_eras_from_era_fields_on_a_mixed_store(tmp_path: Path) -> None:
    """W4-3: read_rows' version-ranked collapse serves ONE row per sid, so a sid
    holding both eras had its transcript row swallowed by the higher-versioned
    event row and the corpus census under-counted. The census counts per
    (era, sid) from era fields."""
    kc.append_facts(
        [
            {
                "facts_version": kb.TRANSCRIPT_FACTS_VERSION,
                "era": "transcript",
                "sid": "abcd9999",
                "day": "2026-06-05",
                "events": DASH,
                "lines_total": 3,
            },
            {
                "facts_version": kc.FACTS_VERSION,
                "sid": "abcd9999",
                "day": "2026-08-18",
                "events": {},
                "lines_total": 1,
            },
        ]
    )
    text = kb.render_report()
    assert "1 transcript-era session(s)" in text, "the event row must not swallow the census"
    assert "1 event-era session(s)" in text
