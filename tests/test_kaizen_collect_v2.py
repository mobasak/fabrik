"""T06 collector v2 — behavior tests (ticket: T06-collector-v2.md).

Every test isolates KAIZEN_EVENTS_DIR / KAIZEN_STATE_DIR (autouse fixture) and every
daily() call gets explicit tmp paths + a stub holes_fn + no_mail — nothing here ever
touches the operator's real ~/.claude/state.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))

import kaizen_collect_v2 as kc  # noqa: E402

GOLDEN = REPO / "tests" / "fixtures" / "kaizen-golden"
DASH = kc.DASH

LOG_STUB = "# log\n\n| " + " | ".join(kc.COLUMNS) + " |\n|" + "---|" * len(kc.COLUMNS) + "\n"


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing in this suite may write the operator's real ~/.claude/state."""
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events-env"))
    monkeypatch.setenv("KAIZEN_STATE_DIR", str(tmp_path / "state-env"))
    monkeypatch.setenv("KAIZEN_GOLDEN_DIR", str(GOLDEN))


def _line(sid: str, event: str, ts: str, project: str | None = "proj-a", **fields: object) -> str:
    row: dict[str, object] = {
        "schema": 1,
        "ts": ts,
        "sid": sid,
        "sid_source": "explicit",
        "event": event,
        "exposure": {
            "commit": "x",
            "account": "x",
            "model": "unknown",
            "headless": False,
            "plan_era": "—",
        },
    }
    if project is not None:
        row["exposure"]["project"] = project  # type: ignore[index]
    row.update(fields)
    return json.dumps(row, ensure_ascii=False)


def _session(dirp: Path, sid: str, lines: list[str]) -> Path:
    dirp.mkdir(parents=True, exist_ok=True)
    path = dirp / f"{sid}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── registry: paired counters are a SCHEMA constraint ────────────────────────────────


def test_registry_refuses_unpaired_definition() -> None:
    with pytest.raises(ValueError, match="unpaired|no counter_metric"):
        kc.validate_registry([{"id": "lonely", "version": 1, "formula": "x"}])


def test_registry_refuses_unregistered_counter() -> None:
    with pytest.raises(ValueError, match="unregistered counter"):
        kc.validate_registry([{"id": "a", "version": 1, "formula": "x", "counter_metric": "ghost"}])


def test_registry_refuses_self_pair() -> None:
    with pytest.raises(ValueError, match="itself"):
        kc.validate_registry([{"id": "a", "version": 1, "formula": "x", "counter_metric": "a"}])


def test_registry_m1_set_loads_with_hashes() -> None:
    reg = kc.registry()
    assert set(reg) == {
        "rules_compliance",
        "terminator_spam",
        "premature_stop_rate",
        "first_attempt_gate_pass",
        "gate_failure_taxonomy",
        "rule_activation",
        "unclassified_rate",
        "hole_count",
    }
    for mid, d in reg.items():
        assert d["counter_metric"] in reg and d["counter_metric"] != mid
        assert isinstance(d["hash"], str) and len(d["hash"]) == 64


# ── the golden-corpus assertion gate — refusal BEFORE publication ─────────────────────


def _refusal_run(
    tmp_path: Path, golden: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, Path, Path, Path]:
    ev = tmp_path / "events"
    st = tmp_path / "state"
    ev.mkdir(exist_ok=True)
    log = tmp_path / "log.md"
    log.write_text(LOG_STUB, encoding="utf-8")
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(ev))  # the alarm event must land HERE
    rc = kc.daily(
        dt.date(2026, 8, 18),
        events=ev,
        state=st,
        golden=golden,
        log_paths=[log],
        no_mail=True,
        holes_fn=lambda d: 0,
    )
    return rc, ev, st, log


def test_golden_mismatch_refuses_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corpus mismatch exits non-zero, emits instrument_alarm, publishes NOTHING,
    and the daily row renders `—` (the ticket's refusal semantics)."""
    tampered = tmp_path / "golden"
    shutil.copytree(GOLDEN, tampered)
    exp = json.loads((tampered / "expected.json").read_text(encoding="utf-8"))
    exp["sessions"]["golden-alpha"]["lines_total"] += 1
    (tampered / "expected.json").write_text(json.dumps(exp), encoding="utf-8")

    rc, ev, st, log = _refusal_run(tmp_path, tampered, monkeypatch)

    assert rc != 0, "a golden mismatch must exit non-zero"
    assert not (st / "series").exists(), "a refused run must publish NO series"
    assert not kc.facts_path(st).exists(), "a refused run must derive NO facts"
    alarms = [p for p in ev.glob("*.jsonl") if "instrument_alarm" in p.read_text(encoding="utf-8")]
    assert alarms, "a refused run must emit an instrument_alarm event"
    text = log.read_text(encoding="utf-8")
    assert "2026-08-18" in text
    row = next(ln for ln in text.splitlines() if ln.startswith("| 2026-08-18"))
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert cells[1:] == [DASH] * (len(kc.COLUMNS) - 1), "the refused row must be all dashes"


def test_golden_missing_expectations_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate fails CLOSED: no expected.json means no publication, not a free pass."""
    bare = tmp_path / "golden"
    bare.mkdir()
    shutil.copy(GOLDEN / "golden-alpha.jsonl", bare / "golden-alpha.jsonl")
    rc, _, st, _ = _refusal_run(tmp_path, bare, monkeypatch)
    assert rc != 0
    assert not (st / "series").exists()


def test_golden_unlabelled_extra_session_refuses(tmp_path: Path) -> None:
    """A fixture added without a hand label is a mismatch, never silently derived."""
    extra = tmp_path / "golden"
    shutil.copytree(GOLDEN, extra)
    shutil.copy(extra / "golden-alpha.jsonl", extra / "golden-extra.jsonl")
    # sid must match the stem to derive cleanly — rewrite it.
    text = (extra / "golden-extra.jsonl").read_text(encoding="utf-8")
    (extra / "golden-extra.jsonl").write_text(
        text.replace("golden-alpha", "golden-extra"), encoding="utf-8"
    )
    assert kc.golden_check(extra), "an unlabelled session must be a mismatch"


def test_golden_corpus_derives_clean() -> None:
    assert kc.golden_check(GOLDEN) == []


# ── duplex parsing predicates — good counts, malformed lands in unclassified_rate ────

_TS = "2026-08-18T10:00:00.000+00:00"


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("", "blank-line"),
        ('{"schema":1,"ts":"2026-08-18T1', "unparseable-json"),
        ("[1,2]", "not-an-object"),
    ],
)
def test_parse_line_simple_rejects(raw: str, reason: str) -> None:
    row, got = kc.parse_line(raw, "s1")
    assert row is None and got == reason


def test_parse_line_unsupported_schema() -> None:
    raw = json.loads(_line("s1", "stop_pass", _TS))
    raw["schema"] = 99
    row, reason = kc.parse_line(json.dumps(raw), "s1")
    assert row is None and reason == "unsupported-schema"


def test_parse_line_missing_event() -> None:
    raw = json.loads(_line("s1", "stop_pass", _TS))
    del raw["event"]
    row, reason = kc.parse_line(json.dumps(raw), "s1")
    assert row is None and reason == "missing-event"


def test_parse_line_sid_file_mismatch() -> None:
    row, reason = kc.parse_line(_line("someone-else", "stop_pass", _TS), "s1")
    assert row is None and reason == "sid-file-mismatch"


def test_parse_line_invalid_ts() -> None:
    row, reason = kc.parse_line(_line("s1", "stop_pass", "not-a-time"), "s1")
    assert row is None and reason == "invalid-ts"


def test_parse_line_malformed_gate_run() -> None:
    bad = _line("s1", "gate_run", _TS, status="success", checks="not-a-list")
    row, reason = kc.parse_line(bad, "s1")
    assert row is None and reason == "malformed-gate_run"
    good = _line(
        "s1", "gate_run", _TS, status="success", checks=[{"name": "ruff", "outcome": "pass"}]
    )
    row, reason = kc.parse_line(good, "s1")
    assert row is not None and reason is None


def test_parse_line_unknown_run_close_verdict() -> None:
    bad = _line("s1", "run_close", _TS, verdict="maybe")
    row, reason = kc.parse_line(bad, "s1")
    assert row is None and reason == "unknown-run_close-verdict"
    good = _line("s1", "run_close", _TS, verdict="done", evidence_hash="h")
    assert kc.parse_line(good, "s1")[1] is None


def test_parse_line_malformed_death_and_round() -> None:
    assert kc.parse_line(_line("s1", "death", _TS), "s1")[1] == "malformed-death"
    assert kc.parse_line(_line("s1", "round", _TS, n="three"), "s1")[1] == "malformed-round"
    assert kc.parse_line(_line("s1", "round", _TS, n=True), "s1")[1] == "malformed-round"
    assert kc.parse_line(_line("s1", "round", _TS, n=3), "s1")[1] is None
    ok = json.loads(_line("s1", "death", _TS, reconstructed=True))
    ok["class"] = "rate_limit"
    ok["sid_source"] = "join"
    assert kc.parse_line(json.dumps(ok), "s1")[1] is None


# ── consumer-side provenance honesty (T03/T05 forward note) ───────────────────────────


def test_provenance_anomaly_none_with_real_sid() -> None:
    raw = json.loads(_line("s1", "stop_pass", _TS))
    raw["sid_source"] = "none"
    row, reason = kc.parse_line(json.dumps(raw), "s1")
    assert row is None and reason == "provenance-anomaly"


def test_provenance_anomaly_env_with_unknown_sid(tmp_path: Path) -> None:
    # sid "unknown" with sid_source claiming env — the inverse anomaly. It can only
    # appear inside unknown.jsonl (sid == stem), where the bucket rule already counts
    # every line as unattributable — the anomaly never slips through as a good line.
    raw = json.loads(_line("unknown", "stop_pass", _TS))
    raw["sid_source"] = "env"
    row, reason = kc.parse_line(json.dumps(raw), "unknown")
    assert row is None and reason == "unattributable-sid"


def test_join_sid_source_is_not_an_anomaly() -> None:
    raw = json.loads(_line("s1", "session_end", _TS))
    raw["sid_source"] = "join"
    row, reason = kc.parse_line(json.dumps(raw), "s1")
    assert row is not None and reason is None


def test_unknown_bucket_lines_are_unattributable(tmp_path: Path) -> None:
    path = _session(
        tmp_path / "ev",
        "unknown",
        [
            _line("unknown", "gate_run", _TS, status="success", checks=[]).replace(
                '"sid_source": "explicit"', '"sid_source": "none"'
            )
        ],
    )
    row = kc.derive_session(path)
    assert row is not None
    assert row["lines_unclassified"] == 1
    assert row["unclassified_reasons"] == {"unattributable-sid": 1}
    assert row["events"] == {}


# ── derivation: never crash, never silently skip ──────────────────────────────────────


def test_derive_session_mixed_good_and_malformed(tmp_path: Path) -> None:
    lines = [
        _line("s1", "session_start", "2026-08-18T10:00:00.000+00:00", cwd="/opt/x"),
        '{"torn',
        _line("s1", "run_open", "2026-08-18T10:05:00.000+00:00", command="c", phases=1),
        _line("s1", "run_close", "2026-08-18T10:30:00.000+00:00", verdict="maybe"),
        _line(
            "s1",
            "run_close",
            "2026-08-18T11:00:00.000+00:00",
            verdict="done",
            evidence_hash="h",
        ),
        _line("s1", "stop_pass", "2026-08-18T12:00:00.000+00:00", outcome="clean"),
    ]
    row = kc.derive_session(_session(tmp_path / "ev", "s1", lines))
    assert row is not None
    assert row["lines_total"] == 6
    assert row["lines_unclassified"] == 2
    assert row["unclassified_reasons"] == {
        "unparseable-json": 1,
        "unknown-run_close-verdict": 1,
    }
    assert row["events"] == {
        "session_start": 1,
        "run_open": 1,
        "run_close": 1,
        "stop_pass": 1,
    }
    assert row["runs"] == {
        "opened": 1,
        "done": 1,
        "done_evidenced": 1,
        "blocked": 0,
        "rounds_max": 0,
    }
    assert row["first_ts"].startswith("2026-08-18T10:00:00")
    assert row["last_ts"].startswith("2026-08-18T12:00:00")


# ── the concurrency flag — window intersection AND equal project ──────────────────────


def _windowed(dirp: Path, sid: str, proj: str | None, lo: str, hi: str) -> Path:
    return _session(
        dirp,
        sid,
        [
            _line(sid, "session_start", lo, project=proj, cwd="/opt/x"),
            _line(sid, "stop_pass", hi, project=proj, outcome="clean"),
        ],
    )


def test_concurrency_requires_overlap_and_equal_project(tmp_path: Path) -> None:
    d = tmp_path / "ev"
    paths = [
        _windowed(d, "a", "p1", "2026-08-18T10:00:00+00:00", "2026-08-18T12:00:00+00:00"),
        _windowed(d, "b", "p1", "2026-08-18T11:00:00+00:00", "2026-08-18T13:00:00+00:00"),
        _windowed(d, "c", "p2", "2026-08-18T10:00:00+00:00", "2026-08-18T12:00:00+00:00"),
        _windowed(d, "e", "p1", "2026-08-18T14:00:00+00:00", "2026-08-18T15:00:00+00:00"),
    ]
    rows = {r["sid"]: r for r in kc.derive_batch(paths)}
    assert rows["a"]["concurrent"] is True
    assert rows["b"]["concurrent"] is True
    assert rows["c"]["concurrent"] is False, "same window, DIFFERENT project — not concurrent"
    assert rows["e"]["concurrent"] is False, "same project, DISJOINT window — not concurrent"


def test_missing_project_excluded_and_counted(tmp_path: Path) -> None:
    d = tmp_path / "ev"
    paths = [
        _windowed(d, "a", "p1", "2026-08-18T10:00:00+00:00", "2026-08-18T12:00:00+00:00"),
        _windowed(d, "n", None, "2026-08-18T10:00:00+00:00", "2026-08-18T12:00:00+00:00"),
    ]
    rows = {r["sid"]: r for r in kc.derive_batch(paths)}
    assert rows["n"]["concurrent"] is None, "missing project is EXCLUDED, never guessed"
    assert rows["n"]["concurrent_reason"] == "missing exposure.project"
    metrics = kc.compute_metrics(list(rows.values()), holes=0)
    m = metrics["unclassified_rate"]
    assert m.measurable
    # 0 bad lines + 1 excluded session over 4 lines + 2 sessions
    assert (m.numerator, m.denominator) == (1, 6)


# ── the derived-facts store: append-only, re-derived only at version bump ────────────


def test_facts_append_only_and_version_bump(tmp_path: Path) -> None:
    st = tmp_path / "state"
    row_v1 = {
        "facts_version": 1,
        "sid": "s1",
        "day": "2026-08-18",
        "last_ts": "2026-08-18T10:00:00",
    }
    assert kc.append_facts([row_v1], st) == 1
    assert kc.append_facts([row_v1], st) == 0, "a session is never re-derived at the same version"
    before = kc.facts_path(st).read_bytes()

    row_v2 = dict(row_v1, facts_version=2)
    assert kc.append_facts([row_v2], st) == 1, "a version bump re-derives"
    after = kc.facts_path(st).read_bytes()
    assert after.startswith(before), "the store is append-only — old rows survive verbatim"
    rows = kc.read_rows(state=st)
    assert len(rows) == 1 and rows[0]["facts_version"] == 2, "read_rows serves the newest version"


def test_read_rows_since_filter(tmp_path: Path) -> None:
    st = tmp_path / "state"
    kc.append_facts(
        [
            {"facts_version": 1, "sid": "old", "last_ts": "2026-08-10T09:00:00"},
            {"facts_version": 1, "sid": "new", "last_ts": "2026-08-18T09:00:00"},
            {"facts_version": 1, "sid": "undated", "last_ts": None},
        ],
        st,
    )
    assert {r["sid"] for r in kc.read_rows(state=st)} == {"old", "new", "undated"}
    assert {r["sid"] for r in kc.read_rows(since="2026-08-15", state=st)} == {"new"}


# ── series: append-only proven by hash comparison; day-idempotent ─────────────────────


def test_series_version_bump_leaves_v1_byte_identical(tmp_path: Path) -> None:
    st = tmp_path / "state"
    rows = kc.derive_batch(sorted(GOLDEN.glob("*.jsonl")))
    metrics = kc.compute_metrics(rows, holes=1)
    reg_v1 = kc.registry()
    kc.publish_series("2026-08-18", metrics, reg_v1, st)
    v1_files = sorted((st / "series").glob("*@v1.jsonl"))
    assert v1_files, "measurable metrics must publish v1 series"
    hashes_before = {p: p.read_bytes() for p in v1_files}

    reg_v2 = {
        mid: {**d, "version": 2, "hash": kc._def_hash({**d, "version": 2})}
        for mid, d in reg_v1.items()
    }
    kc.publish_series("2026-08-18", metrics, reg_v2, st)
    assert all(p.read_bytes() == hashes_before[p] for p in v1_files), (
        "a definition change writes a NEW versioned series — v1 stays byte-identical"
    )
    assert sorted((st / "series").glob("*@v2.jsonl")), "v2 series files must exist"


def test_series_day_is_idempotent(tmp_path: Path) -> None:
    st = tmp_path / "state"
    rows = kc.derive_batch(sorted(GOLDEN.glob("*.jsonl")))
    metrics = kc.compute_metrics(rows, holes=1)
    reg = kc.registry()
    first = kc.publish_series("2026-08-18", metrics, reg, st)
    assert first
    again = kc.publish_series("2026-08-18", metrics, reg, st)
    assert again == [], "a day already published is never re-appended"
    path = kc.series_path("rules_compliance", 1, st)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_unmeasurable_metric_publishes_nothing(tmp_path: Path) -> None:
    st = tmp_path / "state"
    metrics = kc.compute_metrics([], holes=None, holes_reason="no coroner")
    assert kc.publish_series("2026-08-18", metrics, kc.registry(), st) == []
    assert not (st / "series").exists(), "a `—` never becomes a published number"


# ── honesty rendering — `—` with reason, per metric ───────────────────────────────────


@pytest.mark.parametrize(
    "mid",
    [
        "rules_compliance",
        "terminator_spam",
        "premature_stop_rate",
        "first_attempt_gate_pass",
        "gate_failure_taxonomy",
        "rule_activation",
        "unclassified_rate",
        "hole_count",
    ],
)
def test_every_metric_renders_dash_with_reason_when_unmeasurable(mid: str) -> None:
    metrics = kc.compute_metrics([], holes=None, holes_reason="coroner unavailable: test")
    m = metrics[mid]
    assert m.measurable is False
    assert m.cell == DASH, "an unmeasurable metric renders the dash, never a fabricated 0"
    assert m.detail, "the dash always carries its reason"


def test_metric_values_over_the_golden_rows() -> None:
    rows = kc.derive_batch(sorted(GOLDEN.glob("*.jsonl")))
    metrics = kc.compute_metrics(rows, holes=3)
    assert (metrics["rules_compliance"].numerator, metrics["rules_compliance"].denominator) == (
        1,
        2,
    )
    assert (metrics["terminator_spam"].numerator, metrics["terminator_spam"].denominator) == (
        2,
        2,
    )
    assert (
        metrics["premature_stop_rate"].numerator,
        metrics["premature_stop_rate"].denominator,
    ) == (1, 8)
    assert (
        metrics["first_attempt_gate_pass"].numerator,
        metrics["first_attempt_gate_pass"].denominator,
    ) == (0, 1)
    assert metrics["gate_failure_taxonomy"].value == {"Doc Sync Matrix": 1}
    assert (metrics["rule_activation"].numerator, metrics["rule_activation"].denominator) == (
        0,
        2,
    )
    # 10 unclassified lines + 1 concurrency-excluded session over 33 lines + 5 sessions
    assert (
        metrics["unclassified_rate"].numerator,
        metrics["unclassified_rate"].denominator,
    ) == (11, 38)
    assert metrics["hole_count"].cell == "3"


# ── the kaizen-log row: ISO-week idempotence + analyst-cell preservation ──────────────


def test_log_row_iso_week_idempotence_and_analyst_preservation(tmp_path: Path) -> None:
    log = tmp_path / "log.md"
    log.write_text(LOG_STUB, encoding="utf-8")
    monday = ["2026-08-17", "50% (1/2)", "1 occ / 1 cls", DASH, "2.0 (n=1)", DASH, DASH, DASH]
    assert kc.upsert_log_row(log, monday)
    # The analyst fills their cells mid-week (positions 6 and 7).
    lines = log.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("| 2026-08-17"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            cells[6], cells[7] = "fixed the gate", "filed spec-42"
            lines[i] = "| " + " | ".join(cells) + " |"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Tuesday, same ISO week: the row UPDATES in place; analyst cells survive; a
    # mechanical `—` yields to the analyst's earlier value — never stamped back.
    tuesday = ["2026-08-18", "67% (2/3)", DASH, DASH, "3.0 (n=2)", DASH, DASH, DASH]
    assert kc.upsert_log_row(log, tuesday)
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.startswith("| 2026")]
    assert len(lines) == 1, "a second run in the same ISO week UPDATES, never appends"
    cells = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    assert cells[0] == "2026-08-18"
    assert cells[1] == "67% (2/3)", "a fresher mechanical value wins"
    assert cells[2] == "1 occ / 1 cls", "a mechanical dash yields to the earlier real value"
    assert cells[6] == "fixed the gate" and cells[7] == "filed spec-42", (
        "the analysis half's cells survive the re-run"
    )
    # A new ISO week appends a second row.
    assert kc.upsert_log_row(log, ["2026-08-24", "10% (1/10)"] + [DASH] * 6)
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.startswith("| 2026")]
    assert len(lines) == 2


# ── daily mode end to end (tmp everything) ────────────────────────────────────────────


def _green_daily(tmp_path: Path, day: dt.date) -> tuple[int, Path, Path, Path]:
    ev = tmp_path / "events"
    st = tmp_path / "state"
    ev.mkdir(exist_ok=True)
    for f in GOLDEN.glob("*.jsonl"):
        shutil.copy(f, ev / f.name)  # fresh mtime = today
    log = tmp_path / "log.md"
    log.write_text(LOG_STUB, encoding="utf-8")
    rc = kc.daily(
        day,
        events=ev,
        state=st,
        golden=GOLDEN,
        log_paths=[log],
        no_mail=True,
        holes_fn=lambda d: 2,
    )
    return rc, ev, st, log


def test_daily_green_path_publishes(tmp_path: Path) -> None:
    rc, _, st, log = _green_daily(tmp_path, dt.date.today())
    assert rc == 0
    rows = kc.read_rows(state=st)
    assert len(rows) == 5, "all five golden sessions derive into facts"
    assert any((st / "series").glob("*@v1.jsonl")), "series rows published"
    text = log.read_text(encoding="utf-8")
    assert f"| {dt.date.today().isoformat()} |" in text, "the kaizen-log row landed"


def test_daily_rerun_never_reparses(tmp_path: Path) -> None:
    day = dt.date.today()
    rc, _, st, _ = _green_daily(tmp_path, day)
    assert rc == 0
    facts_before = kc.facts_path(st).read_bytes()
    rc = kc.daily(
        day,
        events=tmp_path / "events",
        state=st,
        golden=GOLDEN,
        log_paths=[tmp_path / "log.md"],
        no_mail=True,
        holes_fn=lambda d: 2,
    )
    assert rc == 0
    assert kc.facts_path(st).read_bytes() == facts_before, (
        "a session already derived at this facts_version is NEVER re-parsed daily"
    )


def test_env_overrides_are_honored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "e"))
    monkeypatch.setenv("KAIZEN_STATE_DIR", str(tmp_path / "s"))
    assert kc.events_dir() == tmp_path / "e"
    assert kc.state_dir() == tmp_path / "s"
    assert kc.facts_path() == tmp_path / "s" / "derived-facts.jsonl"


# ── acceptance round 1 fixups (coordinator findings 1-5, red-first) ──────────────────


def _unknown_line(ts: str) -> str:
    row = json.loads(_line("unknown", "gate_run", ts, status="success", checks=[]))
    row["sid_source"] = "none"
    return json.dumps(row, ensure_ascii=False)


def _backdate(path: Path, day: dt.date) -> None:
    import os
    import time as _time

    stamp = _time.mktime(dt.datetime.combine(day, dt.time(12, 0)).timetuple())
    os.utime(path, (stamp, stamp))


def _daily_args(tmp_path: Path) -> dict:
    log = tmp_path / "log.md"
    if not log.exists():
        log.write_text(LOG_STUB, encoding="utf-8")
    return {
        "events": tmp_path / "events",
        "state": tmp_path / "state",
        "golden": GOLDEN,
        "log_paths": [log],
        "no_mail": True,
        "holes_fn": lambda d: 0,
    }


def test_grown_unknown_accumulator_reflected_on_later_day(tmp_path: Path) -> None:
    """F1 (SEVERE): unknown.jsonl grows forever — day-2 growth must be visible to
    read_rows, not frozen at day-1's counts by a derive-once-ever key."""
    ev = tmp_path / "events"
    ev.mkdir()
    yesterday = dt.date.today() - dt.timedelta(days=1)
    unk = ev / "unknown.jsonl"
    unk.write_text(_unknown_line(_TS) + "\n" + _unknown_line(_TS) + "\n", encoding="utf-8")
    _backdate(unk, yesterday)
    assert kc.daily(yesterday, **_daily_args(tmp_path)) == 0
    row = next(r for r in kc.read_rows(state=tmp_path / "state") if r["sid"] == "unknown")
    assert row["lines_total"] == 2

    with open(unk, "a", encoding="utf-8") as fh:
        for _ in range(10):
            fh.write(_unknown_line(_TS) + "\n")  # mtime -> today
    assert kc.daily(dt.date.today(), **_daily_args(tmp_path)) == 0
    row = next(r for r in kc.read_rows(state=tmp_path / "state") if r["sid"] == "unknown")
    assert row["lines_total"] == 12, "day-2 growth of the accumulator must be REFLECTED"
    assert row["lines_unclassified"] == 12


def test_grown_named_session_rederived_on_later_day_append_only(tmp_path: Path) -> None:
    """F1 (SEVERE): a resumed session file that grows onto a later day derives AGAIN
    into a NEW appended row; history stays verbatim (append-only)."""
    ev = tmp_path / "events"
    ev.mkdir()
    yesterday = dt.date.today() - dt.timedelta(days=1)
    grow = ev / "grow.jsonl"
    grow.write_text(
        _line("grow", "session_start", "2026-08-18T10:00:00.000+00:00", cwd="/opt/x")
        + "\n"
        + _line("grow", "stop_pass", "2026-08-18T11:00:00.000+00:00", outcome="clean")
        + "\n",
        encoding="utf-8",
    )
    _backdate(grow, yesterday)
    assert kc.daily(yesterday, **_daily_args(tmp_path)) == 0
    st = tmp_path / "state"
    before = kc.facts_path(st).read_bytes()

    with open(grow, "a", encoding="utf-8") as fh:
        fh.write(
            _line("grow", "stop_pass", "2026-08-19T09:00:00.000+00:00", outcome="clean") + "\n"
        )
    assert kc.daily(dt.date.today(), **_daily_args(tmp_path)) == 0
    after = kc.facts_path(st).read_bytes()
    assert after.startswith(before), "the store is append-only — day-1 rows survive verbatim"
    row = next(r for r in kc.read_rows(state=st) if r["sid"] == "grow")
    assert row["lines_total"] == 3, "the grown session's later-day state must be visible"
    assert row["day"] == dt.date.today().isoformat()


def test_read_rows_since_boundary_is_width_independent(tmp_path: Path) -> None:
    """F2: equal instants must compare equal whatever the fraction width — parsed
    datetimes, never strings."""
    st = tmp_path / "state"
    kc.append_facts(
        [
            {"facts_version": 1, "sid": "bare", "last_ts": "2026-08-15T10:00:00+00:00"},
            {"facts_version": 1, "sid": "milli", "last_ts": "2026-08-15T10:00:00.000+00:00"},
            {"facts_version": 1, "sid": "earlier", "last_ts": "2026-08-15T09:59:59.999+00:00"},
        ],
        st,
    )
    for since in ("2026-08-15T10:00:00.000+00:00", "2026-08-15T10:00:00+00:00"):
        got = {r["sid"] for r in kc.read_rows(since=since, state=st)}
        assert got == {"bare", "milli"}, f"inclusive boundary must hold for since={since}"


def test_derived_timestamps_are_millisecond_width(tmp_path: Path) -> None:
    """F2: first_ts/last_ts carry a fixed millisecond width (the emitter's format)."""
    row = kc.derive_session(
        _session(
            tmp_path / "ev",
            "s1",
            [_line("s1", "stop_pass", "2026-08-18T10:00:00.000+00:00", outcome="clean")],
        )
    )
    assert row is not None
    assert row["first_ts"] == "2026-08-18T10:00:00.000+00:00"
    assert row["last_ts"] == "2026-08-18T10:00:00.000+00:00"


def test_read_rows_unparseable_ts_included_with_warn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F2 disposition: a corrupt last_ts row rides through a since filter VISIBLY
    (included + stderr warn) — silent exclusion would vanish data."""
    st = tmp_path / "state"
    kc.append_facts(
        [
            {"facts_version": 1, "sid": "ok", "last_ts": "2026-08-18T10:00:00.000+00:00"},
            {"facts_version": 1, "sid": "corrupt", "last_ts": "garbage"},
        ],
        st,
    )
    got = {r["sid"] for r in kc.read_rows(since="2026-08-15", state=st)}
    assert got == {"ok", "corrupt"}
    assert "corrupt" in capsys.readouterr().err


def test_registry_refuses_nonreciprocal_pairs() -> None:
    """F3: a 3-cycle (a->b->c->a) must raise — counter pairs are reciprocal."""
    with pytest.raises(ValueError, match="reciprocal"):
        kc.validate_registry(
            [
                {"id": "a", "version": 1, "formula": "x", "counter_metric": "b"},
                {"id": "b", "version": 1, "formula": "x", "counter_metric": "c"},
                {"id": "c", "version": 1, "formula": "x", "counter_metric": "a"},
            ]
        )


def test_project_majority_tie_breaks_deterministically(tmp_path: Path) -> None:
    """F4: an equal-count project tie resolves to the lexicographically first name,
    never insertion order."""
    row = kc.derive_session(
        _session(
            tmp_path / "ev",
            "s1",
            [
                _line("s1", "session_start", _TS, project="zeta", cwd="/x"),
                _line("s1", "stop_pass", "2026-08-18T11:00:00.000+00:00", project="alpha"),
            ],
        )
    )
    assert row is not None
    assert row["project"] == "alpha"


def test_pipe_bearing_analyst_cell_survives_upsert(tmp_path: Path) -> None:
    """F5: a literal pipe inside the last analyst cell must survive a same-week
    upsert intact — never truncated by a naive split."""
    log = tmp_path / "log.md"
    log.write_text(LOG_STUB, encoding="utf-8")
    assert kc.upsert_log_row(
        log, ["2026-08-17", "50% (1/2)", "1 occ / 1 cls", DASH, "2.0 (n=1)", DASH, DASH, DASH]
    )
    lines = log.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("| 2026-08-17"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            cells[6] = "fixed the gate"
            cells[7] = "filed spec-42 | mailed fleet"  # the analyst's literal pipe
            lines[i] = "| " + " | ".join(cells) + " |"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert kc.upsert_log_row(log, ["2026-08-18", "67% (2/3)", DASH, DASH, DASH, DASH, DASH, DASH])
    rows = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.startswith("| 2026")]
    assert len(rows) == 1
    raw = rows[0].strip().strip("|").split("|")
    rejoined = [c.strip() for c in raw[: len(kc.COLUMNS) - 1]] + [
        "|".join(raw[len(kc.COLUMNS) - 1 :]).strip()
    ]
    assert rejoined[6] == "fixed the gate"
    assert rejoined[7] == "filed spec-42 | mailed fleet", "the pipe-bearing cell survives whole"


# ── acceptance round 2 (fix-residue sweep, red-first) ────────────────────────────────


def test_published_day_series_never_recounts_earlier_days(tmp_path: Path) -> None:
    """R2-F1 (SEVERE): the exact repro — unknown.jsonl 2 lines day-1, +10 day-2.
    Day-2's PUBLISHED series value must be the day's delta (10), never the
    cumulative re-count (12)."""
    ev = tmp_path / "events"
    ev.mkdir()
    st = tmp_path / "state"
    yesterday = dt.date.today() - dt.timedelta(days=1)
    unk = ev / "unknown.jsonl"
    unk.write_text(_unknown_line(_TS) + "\n" + _unknown_line(_TS) + "\n", encoding="utf-8")
    _backdate(unk, yesterday)
    assert kc.daily(yesterday, **_daily_args(tmp_path)) == 0
    spath = kc.series_path("unclassified_rate", 1, st)
    rows = [json.loads(ln) for ln in spath.read_text(encoding="utf-8").splitlines()]
    day1 = next(r for r in rows if r["day"] == yesterday.isoformat())
    assert day1["numerator"] == 2

    with open(unk, "a", encoding="utf-8") as fh:
        for _ in range(10):
            fh.write(_unknown_line(_TS) + "\n")  # mtime -> today
    assert kc.daily(dt.date.today(), **_daily_args(tmp_path)) == 0
    rows = [json.loads(ln) for ln in spath.read_text(encoding="utf-8").splitlines()]
    day2 = next(r for r in rows if r["day"] == dt.date.today().isoformat())
    assert day2["numerator"] == 10, (
        "a published day value must never re-count a line already counted in an "
        "earlier published day"
    )
    assert day2["denominator"] == 11  # 10 fresh lines + 1 session


def test_delta_row_shrunk_file_publishes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """R2-F1 disposition: a file that SHRANK (negative delta) warns and yields None —
    that sid publishes nothing that day, never a negative."""
    prev = {
        "sid": "s",
        "facts_version": 1,
        "day": "2026-08-18",
        "lines_total": 5,
        "lines_unclassified": 1,
        "unclassified_reasons": {"unparseable-json": 1},
        "events": {"stop_pass": 4},
        "stop_causes": {},
        "gate": {"runs": 0, "first_status": None, "pass": 0, "fail": 0, "failed_checks": {}},
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 0},
    }
    cur = dict(prev, day="2026-08-19", lines_total=3, events={"stop_pass": 2})
    assert kc.delta_row(cur, prev) is None
    assert "shrank" in capsys.readouterr().err


def test_delta_row_first_gate_status_counts_once() -> None:
    """R2-F1: a session's first gate attempt counts on the day it APPEARED — a later
    day's delta row must not re-claim it."""
    prev = {
        "sid": "s",
        "facts_version": 1,
        "day": "2026-08-18",
        "lines_total": 2,
        "lines_unclassified": 0,
        "unclassified_reasons": {},
        "events": {"gate_run": 1},
        "stop_causes": {},
        "gate": {"runs": 1, "first_status": "failure", "pass": 0, "fail": 1, "failed_checks": {}},
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 0},
    }
    cur = dict(
        prev,
        day="2026-08-19",
        lines_total=3,
        events={"gate_run": 2},
        gate={"runs": 2, "first_status": "failure", "pass": 1, "fail": 1, "failed_checks": {}},
    )
    delta = kc.delta_row(cur, prev)
    assert delta is not None
    assert delta["gate"]["runs"] == 1, "only the day's fresh gate runs"
    assert delta["gate"]["first_status"] is None, "the first attempt was already counted"


def test_read_rows_latest_is_day_order_not_append_order(tmp_path: Path) -> None:
    """R2-F2: an out-of-order backfill (earlier day appended AFTER a later day) must
    not become authoritative — latest = max day within max facts_version."""
    st = tmp_path / "state"
    kc.append_facts([{"facts_version": 1, "sid": "s", "day": "2026-08-19", "lines_total": 12}], st)
    kc.append_facts([{"facts_version": 1, "sid": "s", "day": "2026-08-18", "lines_total": 2}], st)
    rows = kc.read_rows(state=st)
    assert len(rows) == 1
    assert rows[0]["day"] == "2026-08-19", "a day-1 backfill must not shadow day-2's row"


def test_append_facts_dedups_within_one_batch(tmp_path: Path) -> None:
    """R2-F3: two rows with the same (sid, facts_version, day) in ONE call append
    exactly once — the one-row-per-key promise holds against the call's own batch."""
    st = tmp_path / "state"
    row = {"facts_version": 1, "sid": "s", "day": "2026-08-18", "lines_total": 2}
    assert kc.append_facts([row, dict(row)], st) == 1
    assert len(kc.facts_path(st).read_text(encoding="utf-8").splitlines()) == 1


# ── acceptance round 3 (residue sweep, red-first) ────────────────────────────────────


def _gate_row(sid: str, day: str, runs: int, first: str | None, ok: int, bad: int) -> dict:
    return {
        "sid": sid,
        "facts_version": 1,
        "day": day,
        "lines_total": runs,
        "lines_unclassified": 0,
        "unclassified_reasons": {},
        "events": {"gate_run": runs},
        "stop_causes": {},
        "gate": {
            "runs": runs,
            "first_status": first,
            "pass": ok,
            "fail": bad,
            "failed_checks": {},
        },
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 0},
    }


def test_first_attempt_gate_pass_not_diluted_by_continuing_sessions() -> None:
    """R3-F1: a continuing session (first attempt already counted an earlier day)
    must leave the denominator too — the exact two-session two-day repro."""
    # Session A first-failed on day 1; on day 2 it re-runs and passes.
    prev_a = _gate_row("a", "2026-08-18", 1, "failure", 0, 1)
    cur_a = _gate_row("a", "2026-08-19", 2, "failure", 1, 1)
    delta_a = kc.delta_row(cur_a, prev_a)
    assert delta_a is not None
    assert delta_a["gate"]["first_status"] is None  # suppressed, correct (round 2)
    # Session B genuinely first-attempts on day 2 and passes.
    row_b = _gate_row("b", "2026-08-19", 1, "success", 1, 0)

    metrics = kc.compute_metrics([delta_a, row_b], holes=0)
    m = metrics["first_attempt_gate_pass"]
    assert (m.numerator, m.denominator) == (1, 1), (
        "the denominator is sessions whose FIRST attributed gate run happened that "
        "day — a continuing session must not dilute it"
    )
    assert m.value == 1.0


def test_version_bump_day_does_not_recount_earlier_days(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3-F2: a FACTS_VERSION bump on a still-growing file must not republish the
    full cumulative row as that day's delta — the v1-day1 / v2-day2 repro."""
    ev = tmp_path / "events"
    ev.mkdir()
    st = tmp_path / "state"
    yesterday = dt.date.today() - dt.timedelta(days=1)
    # Day 1 was derived under facts_version 1 (2 unknown lines).
    kc.append_facts(
        [
            {
                "facts_version": 1,
                "sid": "unknown",
                "day": yesterday.isoformat(),
                "lines_total": 2,
                "lines_unclassified": 2,
                "unclassified_reasons": {"unattributable-sid": 2},
                "events": {},
                "stop_causes": {},
                "gate": {
                    "runs": 0,
                    "first_status": None,
                    "pass": 0,
                    "fail": 0,
                    "failed_checks": {},
                },
                "runs": {
                    "opened": 0,
                    "done": 0,
                    "done_evidenced": 0,
                    "blocked": 0,
                    "rounds_max": 0,
                },
                "concurrent": None,
                "concurrent_reason": "unattributable-sid",
                "first_ts": None,
                "last_ts": None,
            }
        ],
        st,
    )
    # Day 2: the file has grown to 12 lines and the collector runs at version 2.
    unk = ev / "unknown.jsonl"
    unk.write_text("".join(_unknown_line(_TS) + "\n" for _ in range(12)), encoding="utf-8")
    bumped = tmp_path / "golden-v2"
    shutil.copytree(GOLDEN, bumped)
    exp = json.loads((bumped / "expected.json").read_text(encoding="utf-8"))
    exp["facts_version"] = 2
    (bumped / "expected.json").write_text(json.dumps(exp), encoding="utf-8")
    monkeypatch.setattr(kc, "FACTS_VERSION", 2)

    args = _daily_args(tmp_path)
    args["golden"] = bumped
    assert kc.daily(dt.date.today(), **args) == 0
    spath = kc.series_path("unclassified_rate", 1, st)
    rows = [json.loads(ln) for ln in spath.read_text(encoding="utf-8").splitlines()]
    day2 = next(r for r in rows if r["day"] == dt.date.today().isoformat())
    assert day2["numerator"] == 10, (
        "within one published series no line is counted twice — the bump day must "
        "subtract the cross-version baseline, not republish the cumulative row"
    )


def test_delta_row_map_only_shrink_publishes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """R3-F3: a counter MAP losing a key/count while every scalar stays flat or
    growing is still a shrink — publishes nothing + warn (exercises _sub_map's
    negative branch, which the scalar-shrink test never reaches)."""
    prev = _gate_row("s", "2026-08-18", 0, None, 0, 0)
    prev["lines_total"] = 5
    prev["events"] = {"stop_pass": 4, "stop_block": 1}
    cur = json.loads(json.dumps(prev))
    cur["day"] = "2026-08-19"
    cur["lines_total"] = 5  # scalars flat
    cur["events"] = {"stop_pass": 4}  # the stop_block count vanished
    assert kc.delta_row(cur, prev) is None
    assert "shrank" in capsys.readouterr().err


def test_delta_of_key_always_present() -> None:
    """R3-F4: delta_of is part of the delta-row shape — null on a first-ever row,
    the predecessor's day on a true delta — never absent."""
    first = _gate_row("s", "2026-08-18", 1, "success", 1, 0)
    out = kc.delta_row(first, None)
    assert out is not None
    assert "delta_of" in out and out["delta_of"] is None
    assert "delta_of" not in first, "the store row itself is never mutated"

    cur = _gate_row("s", "2026-08-19", 2, "success", 2, 0)
    cur["lines_total"] = 2
    delta = kc.delta_row(cur, first)
    assert delta is not None
    assert delta["delta_of"] == "2026-08-18"


# ── acceptance round 4 (closing wave) ────────────────────────────────────────────────


def test_dual_ranking_divergence_is_intentional(tmp_path: Path) -> None:
    """R4-F1: the two seams rank DIFFERENTLY on purpose, and this pin keeps a future
    "cleanup" from aligning them. Scenario: row A v1/day-10, row B v2/day-3 (a
    backfilled higher-version row for an earlier day). read_rows serves B — the
    current-state seam, newest schema wins; predecessors' baseline for day-11 is A —
    the chronological seam, a day-delta subtracts the latest CALENDAR baseline
    whatever schema derived it."""
    st = tmp_path / "state"
    kc.append_facts(
        [
            {"facts_version": 1, "sid": "s", "day": "2026-08-10", "lines_total": 10},
            {"facts_version": 2, "sid": "s", "day": "2026-08-03", "lines_total": 3},
        ],
        st,
    )
    (current,) = kc.read_rows(state=st)
    assert current["facts_version"] == 2 and current["day"] == "2026-08-03", (
        "read_rows: current state — newest schema wins, even from an earlier day"
    )
    baseline = kc.predecessors("2026-08-11", state=st)["s"]
    assert baseline["facts_version"] == 1 and baseline["day"] == "2026-08-10", (
        "predecessors: chronological — the latest calendar day wins, whatever version"
    )


def test_delta_darkening_emits_instrument_alarm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R4-F2: a sid darked by a shrink (delta None with a predecessor) must raise the
    same instrument_alarm channel the golden gate uses — stderr alone is invisible
    exactly when eyes are needed (a version bump)."""
    ev = tmp_path / "events"
    ev.mkdir()
    st = tmp_path / "state"
    yesterday = dt.date.today() - dt.timedelta(days=1)
    kc.append_facts(
        [
            {
                "facts_version": 1,
                "sid": "shrink",
                "day": yesterday.isoformat(),
                "lines_total": 5,
                "lines_unclassified": 0,
                "unclassified_reasons": {},
                "events": {"stop_pass": 5},
                "stop_causes": {},
                "gate": {
                    "runs": 0,
                    "first_status": None,
                    "pass": 0,
                    "fail": 0,
                    "failed_checks": {},
                },
                "runs": {
                    "opened": 0,
                    "done": 0,
                    "done_evidenced": 0,
                    "blocked": 0,
                    "rounds_max": 0,
                },
                "concurrent": None,
                "concurrent_reason": "no parseable timestamps",
                "first_ts": None,
                "last_ts": None,
            }
        ],
        st,
    )
    shrunk = ev / "shrink.jsonl"
    shrunk.write_text(  # 3 lines < yesterday's 5 — the file shrank
        "".join(_line("shrink", "stop_pass", _TS, outcome="clean") + "\n" for _ in range(3)),
        encoding="utf-8",
    )
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(ev))  # the alarm must land HERE
    assert kc.daily(dt.date.today(), **_daily_args(tmp_path)) == 0
    alarm_lines = [
        ln
        for p in ev.glob("*.jsonl")
        for ln in p.read_text(encoding="utf-8").splitlines()
        if "instrument_alarm" in ln
    ]
    assert alarm_lines, "a darkened sid must emit instrument_alarm, not just stderr"
    assert any("shrink" in ln and "shrank" in ln for ln in alarm_lines), (
        "the alarm carries the sid and the reason"
    )


def test_first_ever_rows_emit_no_alarm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R4-F2 control: a first-ever row (no predecessor) is not a darkening — a green
    daily run over fresh sessions emits NO instrument_alarm."""
    ev = tmp_path / "events"
    ev.mkdir()
    for f in GOLDEN.glob("*.jsonl"):
        shutil.copy(f, ev / f.name)
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(ev))
    assert kc.daily(dt.date.today(), **_daily_args(tmp_path)) == 0
    assert not any(
        "instrument_alarm" in p.read_text(encoding="utf-8") for p in ev.glob("*.jsonl")
    ), "first-ever absences must not alarm"


def _transcript_era_row(day: str, sid: str = "tr-legacy") -> dict:
    """A T08 backfill row, verbatim shape (kaizen_backfill.derive_transcript_session):
    every event-only field is the DASH string, never a dict."""
    return {
        "facts_version": kc.FACTS_VERSION,
        "era": "transcript",
        "sid": sid,
        "day": day,
        "derived_at": "2026-08-20T00:00:00+00:00",
        "first_ts": None,
        "last_ts": None,
        "project": "fabrik",
        "events": DASH,
        "gate": DASH,
        "runs": DASH,
        "stop_causes": DASH,
        "death_class": DASH,
        "concurrent": None,
        "concurrent_reason": "transcript era: concurrency is event-only",
        "lines_total": 10,
        "lines_unclassified": 2,
        "unclassified_reasons": {"unparseable-json": 2},
        "invocations": {"typed": {}, "skill": {}},
    }


def test_daily_excludes_transcript_era_rows(tmp_path: Path) -> None:
    """T09 era filter (T08's standing finding): the real store holds era:"transcript"
    rows whose day falls in the CURRENT week — daily()'s day/week row selection must
    exclude every non-event-era row, or compute_metrics crashes on their dash strings
    ('str' object has no attribute 'get')."""
    day = dt.date.today()
    st = tmp_path / "state"
    st.mkdir(parents=True)
    assert kc.append_facts([_transcript_era_row(day.isoformat())], st) == 1
    rc, _, st_out, log = _green_daily(tmp_path, day)
    assert rc == 0, "daily() must not crash on a transcript-era row in the day/week window"
    assert st_out == st
    # The transcript row stays in the store (read_rows still serves it for T08's
    # report) but contributes to NO published metric input.
    assert any(r.get("era") == "transcript" for r in kc.read_rows(state=st))
    text = log.read_text(encoding="utf-8")
    assert f"| {day.isoformat()} |" in text, "the kaizen-log row still lands"


def test_predecessors_never_serve_a_transcript_era_baseline(tmp_path: Path) -> None:
    """The delta seam's subtraction base is a published-day baseline; a transcript row
    (dash-string fields, lines counted from prose) must never be one."""
    st = tmp_path / "state"
    st.mkdir(parents=True)
    kc.append_facts([_transcript_era_row("2026-08-10", sid="s")], st)
    assert kc.predecessors("2026-08-11", state=st) == {}, (
        "a transcript-era row must not become a delta baseline"
    )


def test_malformed_log_row_preserved_verbatim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F5: a row that doesn't parse to the table's shape is preserved VERBATIM with a
    stderr warn — never reshaped, never merged into."""
    log = tmp_path / "log.md"
    malformed = "| 2026-08-17 | only | three-cells |"
    log.write_text(LOG_STUB + malformed + "\n", encoding="utf-8")
    assert kc.upsert_log_row(log, ["2026-08-18", "67% (2/3)", DASH, DASH, DASH, DASH, DASH, DASH])
    text = log.read_text(encoding="utf-8")
    assert malformed in text, "the malformed row must survive byte-identical"
    assert "| 2026-08-18 |" in text, "our row still lands (appended alongside, warned)"
    assert "malformed" in capsys.readouterr().err
