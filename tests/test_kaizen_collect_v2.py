"""T06 collector v2 — behavior tests (ticket: T06-collector-v2.md).

Every test isolates KAIZEN_EVENTS_DIR / KAIZEN_STATE_DIR (autouse fixture) and every
daily() call gets explicit tmp paths + a stub holes_fn + no_mail — nothing here ever
touches the operator's real ~/.claude/state.
"""

from __future__ import annotations

import datetime as dt
import json
import os
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
        "death_occurrences",
        "death_classes",
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
    # H2: 0 bad lines over 4 lines — the project-less session is a stratification
    # gap (visible in concurrent_reason), never instrument unhealth.
    assert (m.numerator, m.denominator) == (0, 4)


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
    reg_base = kc.registry()
    kc.publish_series("2026-08-18", metrics, reg_base, st)
    base_files = sorted((st / "series").glob("*@v*.jsonl"))
    assert base_files, "measurable metrics must publish series at their registry versions"
    hashes_before = {p: p.read_bytes() for p in base_files}

    reg_bumped = {
        mid: {
            **d,
            "version": int(d["version"]) + 1,
            "hash": kc._def_hash({**d, "version": int(d["version"]) + 1}),
        }
        for mid, d in reg_base.items()
    }
    kc.publish_series("2026-08-18", metrics, reg_bumped, st)
    assert all(p.read_bytes() == hashes_before[p] for p in base_files), (
        "a definition change writes a NEW versioned series — the old files stay byte-identical"
    )
    assert set((st / "series").glob("*@v*.jsonl")) - set(base_files), (
        "the bumped versions must land in NEW files"
    )


def test_series_day_is_idempotent(tmp_path: Path) -> None:
    st = tmp_path / "state"
    rows = kc.derive_batch(sorted(GOLDEN.glob("*.jsonl")))
    metrics = kc.compute_metrics(rows, holes=1)
    reg = kc.registry()
    first = kc.publish_series("2026-08-18", metrics, reg, st)
    assert first
    again = kc.publish_series("2026-08-18", metrics, reg, st)
    assert again == [], "a day already published is never re-appended"
    path = kc.series_path("rules_compliance", reg["rules_compliance"]["version"], st)
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
    # L5: golden-alpha's first two gate_runs are --check runs — only the 11:40
    # NON-check failure defines its first attempt (0/1 sessions passed first try).
    assert metrics["first_attempt_gate_pass"].measurable
    assert (
        metrics["first_attempt_gate_pass"].numerator,
        metrics["first_attempt_gate_pass"].denominator,
    ) == (0, 1)
    # W2-F1: the taxonomy counts NON-check fails only — the check runs' Doc Sync
    # Matrix fail is diagnostic, never taxonomy.
    assert metrics["gate_failure_taxonomy"].value == {"mypy": 1}
    # H3: every rule_activation occurrence sits in the unknown stream — dash, not 0%.
    assert not metrics["rule_activation"].measurable
    assert "unattributable" in metrics["rule_activation"].detail
    # H2: 10 unclassified lines over 34 lines — lines over lines, no session terms.
    assert (
        metrics["unclassified_rate"].numerator,
        metrics["unclassified_rate"].denominator,
    ) == (10, 34)
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
    # mechanical `—` PUBLISHES (H6 — a fresh honest dash must never republish the
    # earlier number under a new date); only analyst cells yield.
    tuesday = ["2026-08-18", "67% (2/3)", DASH, DASH, "3.0 (n=2)", DASH, DASH, DASH]
    assert kc.upsert_log_row(log, tuesday)
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.startswith("| 2026")]
    assert len(lines) == 1, "a second run in the same ISO week UPDATES, never appends"
    cells = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    assert cells[0] == "2026-08-18"
    assert cells[1] == "67% (2/3)", "a fresher mechanical value wins"
    assert cells[2] == DASH, "a mechanical dash publishes — no stale republish (H6)"
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
    assert any((st / "series").glob("*@v*.jsonl")), "series rows published"
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
    spath = kc.series_path("unclassified_rate", kc.registry()["unclassified_rate"]["version"], st)
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
    assert day2["denominator"] == 10  # 10 fresh lines — lines over lines (H2)


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
    spath = kc.series_path("unclassified_rate", kc.registry()["unclassified_rate"]["version"], st)
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
        "death_classes": DASH,
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


# ── review fix-wave: adjudicated findings, red-first ─────────────────────────────────


def test_daily_selects_files_alive_at_or_after_the_day(tmp_path: Path) -> None:
    """H1: `mtime date == day` permanently excluded unknown.jsonl (it never quiesces)
    and deferred every still-active session — selection is mtime-date >= day."""
    ev = tmp_path / "events"
    ev.mkdir()
    yesterday = dt.date.today() - dt.timedelta(days=1)
    # Both files are STILL BEING WRITTEN — fresh (today) mtime, no backdating.
    (ev / "unknown.jsonl").write_text(_unknown_line(_TS) + "\n", encoding="utf-8")
    _session(ev, "active", [_line("active", "session_start", _TS, cwd="/opt/x")])
    assert kc.daily(yesterday, **_daily_args(tmp_path)) == 0
    sids = {r["sid"]: r for r in kc.read_rows(state=tmp_path / "state")}
    assert "unknown" in sids, "the never-quiescing accumulator must be derived (H1)"
    assert "active" in sids, "a still-active session must get its day row (H1)"
    assert sids["unknown"]["day"] == yesterday.isoformat()


def test_truncated_line_is_envelope_only(tmp_path: Path) -> None:
    """M1: a clipped line (truncated / fields_dropped) lands as reason "truncated"
    with envelope counts only — its partial payload never feeds a distribution."""
    clipped = json.loads(
        _line(
            "t",
            "gate_run",
            _TS,
            status="failure",
            checks=[{"name": f"c{i}", "outcome": "fail"} for i in range(50)],
        )
    )
    clipped["truncated"] = True
    dropped = json.loads(_line("t", "gate_run", "2026-08-18T10:30:00.000+00:00"))
    dropped["truncated"] = True
    dropped["fields_dropped"] = True
    good = _line(
        "t",
        "gate_run",
        "2026-08-18T11:00:00.000+00:00",
        status="success",
        checks=[{"name": "ruff", "outcome": "pass"}],
    )
    path = _session(
        tmp_path / "ev",
        "t",
        [json.dumps(clipped, ensure_ascii=False), json.dumps(dropped, ensure_ascii=False), good],
    )
    row = kc.derive_session(path)
    assert row is not None
    assert row["unclassified_reasons"] == {"truncated": 2}
    assert row["events"] == {"gate_run": 3}, "the envelope (event name) still counts"
    assert row["gate"]["runs"] == 1, "a clipped payload must never feed gate stats"
    assert row["gate"]["failed_checks"] == {}, "no 50-check taxonomy from a clipped line"
    assert row["last_ts"] == "2026-08-18T11:00:00.000+00:00", "envelope ts still windows"


def test_malformed_evidence_hash_and_stop_cause_are_counted(tmp_path: Path) -> None:
    """M8: a malformed run_close.evidence_hash / stop_block.cause is COUNTED with a
    reason, never silently dropped."""
    lines = [
        _line("m8", "run_close", _TS, verdict="done", evidence_hash=42),
        _line("m8", "stop_block", _TS, cause=7, outcome="blocked"),
    ]
    row = kc.derive_session(_session(tmp_path / "ev", "m8", lines))
    assert row is not None
    assert row["unclassified_reasons"].get("malformed-evidence_hash") == 1
    assert row["unclassified_reasons"].get("malformed-stop_block-cause") == 1
    assert row["runs"]["done"] == 1 and row["runs"]["done_evidenced"] == 0
    assert row["stop_causes"] == {}


def test_all_death_classes_kept_not_just_the_last(tmp_path: Path) -> None:
    """M9: every death class in the session survives — never only the last one."""
    lines = [
        _line("d", "death", _TS, **{"class": "rate_limit"}),
        _line("d", "death", "2026-08-18T11:00:00.000+00:00", **{"class": "api_error_stalled"}),
    ]
    row = kc.derive_session(_session(tmp_path / "ev", "d", lines))
    assert row is not None
    assert row["death_classes"] == ["rate_limit", "api_error_stalled"]


def test_first_status_ignores_check_mode_gate_runs(tmp_path: Path) -> None:
    """L5: the Stop hook's automatic --lean --check self-review must never define the
    first attempt — first_status considers only NON-check gate runs."""
    lines = [
        _line(
            "g",
            "gate_run",
            _TS,
            status="failure",
            checks=[],
            mode={"check": True, "lean": True, "systemic": False, "json": True},
        ),
        _line(
            "g",
            "gate_run",
            "2026-08-18T11:00:00.000+00:00",
            status="success",
            checks=[],
            mode={"check": False, "lean": False, "systemic": False, "json": True},
        ),
    ]
    row = kc.derive_session(_session(tmp_path / "ev", "g", lines))
    assert row is not None
    assert row["gate"]["first_status"] == "success"
    assert row["gate"]["runs"] == 2, "check runs still count as runs"


def test_delta_first_status_survives_a_check_only_predecessor() -> None:
    """L5 delta seam: a predecessor whose runs were all --check (first_status None)
    has NOT consumed the session's first attempt — the current row keeps it."""
    base = {
        "sid": "s",
        "facts_version": kc.FACTS_VERSION,
        "events": {},
        "unclassified_reasons": {},
        "stop_causes": {},
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 0},
        "lines_total": 1,
        "lines_unclassified": 0,
    }
    prev = {
        **json.loads(json.dumps(base)),
        "day": "2026-08-17",
        "gate": {"runs": 1, "first_status": None, "pass": 1, "fail": 0, "failed_checks": {}},
    }
    cur = {
        **json.loads(json.dumps(base)),
        "day": "2026-08-18",
        "lines_total": 2,
        "gate": {"runs": 2, "first_status": "success", "pass": 2, "fail": 0, "failed_checks": {}},
    }
    delta = kc.delta_row(cur, prev)
    assert delta is not None
    assert delta["gate"]["first_status"] == "success"


def test_unknown_row_counts_unattributed_event_families(tmp_path: Path) -> None:
    """H3 input: the unknown bucket cannot make session facts, but its event NAMES
    are envelope truth the attribution-honesty guard needs."""
    act = json.loads(_line("unknown", "rule_activation", _TS, packs=[]))
    act["sid_source"] = "none"
    path = _session(
        tmp_path / "ev",
        "unknown",
        [_unknown_line(_TS), json.dumps(act, ensure_ascii=False)],
    )
    row = kc.derive_session(path)
    assert row is not None
    assert row["events"] == {}
    assert row["events_unattributed"] == {"gate_run": 1, "rule_activation": 1}


def test_unclassified_rate_is_lines_over_lines(tmp_path: Path) -> None:
    """H2: numerator = unclassified lines (unknown-stream lines included via their
    unattributable-sid reason); denominator = total lines observed. A session missing
    exposure.project is a stratification gap, NOT instrument unhealth."""
    d = tmp_path / "ev"
    paths = [
        _windowed(d, "a", "p1", "2026-08-18T10:00:00+00:00", "2026-08-18T12:00:00+00:00"),
        _windowed(d, "n", None, "2026-08-18T10:00:00+00:00", "2026-08-18T12:00:00+00:00"),
    ]
    rows = kc.derive_batch(paths)
    m = kc.compute_metrics(rows, holes=0)["unclassified_rate"]
    assert m.measurable
    assert (m.numerator, m.denominator) == (0, 4), (
        "no session-count inflation, no numerator for a mere stratification gap"
    )


def test_rule_activation_dashes_when_family_is_unattributable() -> None:
    """H3: zero attributed rule_activation occurrences while the unknown stream holds
    some → the metric renders — with the reason, never a fabricated 0%."""
    rows = kc.derive_batch(sorted(GOLDEN.glob("*.jsonl")))
    m = kc.compute_metrics(rows, holes=0)["rule_activation"]
    assert not m.measurable
    assert "unattributable" in m.detail


def test_run_record_metrics_dash_below_attribution_floor() -> None:
    """M5: n=1 attributed closure against an unknown-stream mass publishes NOTHING —
    below the documented attribution floor both paired metrics dash together."""

    def _row(sid: str, done: int, unattr: dict) -> dict:
        return {
            "sid": sid,
            "facts_version": kc.FACTS_VERSION,
            "day": "2026-08-18",
            "events": {"run_close": done, "final_block_emitted": done},
            "events_unattributed": unattr,
            "unclassified_reasons": {},
            "stop_causes": {},
            "gate": {"runs": 0, "first_status": None, "pass": 0, "fail": 0, "failed_checks": {}},
            "runs": {
                "opened": done,
                "done": done,
                "done_evidenced": done,
                "blocked": 0,
                "rounds_max": 0,
            },
            "lines_total": done,
            "lines_unclassified": 0,
        }

    starved = [_row("s", 1, {}), _row("unknown", 0, {"run_close": 38})]
    metrics = kc.compute_metrics(starved, holes=0)
    assert not metrics["rules_compliance"].measurable
    assert "run-record events unattributable" in metrics["rules_compliance"].detail
    assert not metrics["terminator_spam"].measurable
    # Control: attribution above the floor stays measured.
    healthy = [_row("s", 10, {}), _row("unknown", 0, {"run_close": 1})]
    metrics = kc.compute_metrics(healthy, holes=0)
    assert metrics["rules_compliance"].measurable
    assert metrics["terminator_spam"].measurable


def test_mechanical_dash_never_republishes_stale_number(tmp_path: Path) -> None:
    """H6: an all-dash mechanical day over a measured earlier row publishes dashes
    under the advanced date — only the ANALYST cells keep the yield rule."""
    log = tmp_path / "log.md"
    log.write_text(LOG_STUB, encoding="utf-8")
    monday = ["2026-08-17", "50% (1/2)", "1 occ / 1 cls", DASH, "2.0 (n=1)", DASH, "note", "filed"]
    assert kc.upsert_log_row(log, monday)
    all_dash = ["2026-08-18"] + [DASH] * (len(kc.COLUMNS) - 1)
    assert kc.upsert_log_row(log, all_dash)
    (line,) = [ln for ln in log.read_text(encoding="utf-8").splitlines() if "| 2026" in ln]
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    assert cells[0] == "2026-08-18", "the date advances"
    assert cells[1] == DASH and cells[2] == DASH and cells[4] == DASH, (
        "a fresh honest dash must never republish yesterday's number"
    )
    assert cells[6] == "note" and cells[7] == "filed", "analyst cells still yield"


def test_daily_validates_registry_before_mutating_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M6: a broken registry must refuse BEFORE any state mutation — alarm + raise,
    nothing derived, nothing published."""
    ev = tmp_path / "events"
    ev.mkdir()
    (ev / "unknown.jsonl").write_text(_unknown_line(_TS) + "\n", encoding="utf-8")
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(ev))

    def _boom() -> dict:
        raise ValueError("unpaired definition")

    monkeypatch.setattr(kc, "registry", _boom)
    with pytest.raises(ValueError, match="unpaired"):
        kc.daily(dt.date.today(), **_daily_args(tmp_path))
    assert not kc.facts_path(tmp_path / "state").exists(), (
        "an invalid registry must be caught BEFORE the store is mutated"
    )
    alarms = [p for p in ev.glob("*.jsonl") if "instrument_alarm" in p.read_text(encoding="utf-8")]
    assert alarms, "the refusal must raise the alarm channel, not only a traceback"


def test_daily_publishes_outcome_tier_series(tmp_path: Path) -> None:
    """M7 + W7-1: the store-derived outcome tier (premature_stop /
    stop_block_causes / review_rounds) publishes its series day from the SAME
    daily pass, DAY-SCOPED — the point is computed over the published day's delta
    rows only (no env window reaches the publish seam), so the fixture session is
    born today."""
    ev = tmp_path / "events"
    st = tmp_path / "state"
    ev.mkdir()
    for f in GOLDEN.glob("*.jsonl"):
        shutil.copy(f, ev / f.name)
    exposure = {
        "commit": "x",
        "account": "x",
        "model": "m",
        "project": "alpha-proj",
        "headless": False,
        "plan_era": "—",
    }
    ts = dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds")
    live_lines = [
        {"schema": 1, "ts": ts, "sid": "live-now", "sid_source": "explicit"} | extra
        for extra in (
            {"event": "stop_pass", "exposure": exposure},
            {"event": "stop_block", "exposure": exposure, "cause": "run-record"},
            {"event": "round", "exposure": exposure, "n": 3},
        )
    ]
    (ev / "live-now.jsonl").write_text(
        "\n".join(json.dumps(o) for o in live_lines) + "\n", encoding="utf-8"
    )
    log = tmp_path / "log.md"
    log.write_text(LOG_STUB, encoding="utf-8")
    rc = kc.daily(
        dt.date.today(),
        events=ev,
        state=st,
        golden=GOLDEN,
        log_paths=[log],
        no_mail=True,
        holes_fn=lambda d: 2,
    )
    assert rc == 0
    import kaizen_outcomes  # noqa: PLC0415

    reg = kaizen_outcomes.registry()
    for mid in ("premature_stop", "stop_block_causes", "review_rounds"):
        path = kc.series_path(mid, int(reg[mid]["version"]), st)
        assert path.exists(), f"{mid} series must gain its day from daily()"
        days = {json.loads(ln)["day"] for ln in path.read_text().splitlines()}
        assert dt.date.today().isoformat() in days


def test_week_rows_are_per_week_latest_not_global(tmp_path: Path) -> None:
    """L1: a sid's later-week row must not evict its earlier-week row from that
    week's read — the latest-per-sid collapse is PER WEEK."""
    st = tmp_path / "state"
    st.mkdir(parents=True)
    base = {
        "sid": "x",
        "facts_version": kc.FACTS_VERSION,
        "events": {},
        "unclassified_reasons": {},
        "stop_causes": {},
        "gate": {"runs": 0, "first_status": None, "pass": 0, "fail": 0, "failed_checks": {}},
        "lines_total": 1,
        "lines_unclassified": 0,
    }
    week1 = {
        **json.loads(json.dumps(base)),
        "day": "2026-08-10",
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 4},
    }
    week2 = {
        **json.loads(json.dumps(base)),
        "day": "2026-08-18",
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 5},
    }
    assert kc.append_facts([week1, week2], st) == 2
    wk = dt.date.fromisoformat("2026-08-10").isocalendar()[:2]
    rows = kc.read_week_rows(wk, state=st)
    assert [r["day"] for r in rows] == ["2026-08-10"], (
        "the earlier week's row must be served for the earlier week"
    )


def test_daily_passes_events_dir_to_coroner_hole_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L4: daily(events=...) must reach the coroner hole probe — the default-source
    probe silently counted a DIFFERENT store's holes."""
    import kaizen_coroner  # noqa: PLC0415

    captured: dict[str, object] = {}

    def _fake_holes(sources: object = None, day: object = None) -> int:
        captured["sources"] = sources
        return 0

    monkeypatch.setattr(kaizen_coroner, "holes", _fake_holes)
    args = _daily_args(tmp_path)
    args["holes_fn"] = None
    args["events"].mkdir(exist_ok=True)
    assert kc.daily(dt.date.today(), **args) == 0
    src = captured.get("sources")
    assert src is not None, "daily must build injected Sources for the probe"
    assert Path(src.events_dir) == args["events"]  # type: ignore[union-attr]


def test_concurrent_append_facts_never_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L6: the read-known-keys -> append seam is under an inter-process lock; two
    writers racing the same key append it exactly once."""
    import threading  # noqa: PLC0415
    import time as _time  # noqa: PLC0415

    st = tmp_path / "state"
    st.mkdir(parents=True)
    row = {"sid": "s", "facts_version": kc.FACTS_VERSION, "day": "2026-08-18"}
    real = kc.known_fact_keys

    def _slow(state: Path | None = None) -> set:
        out = real(state)
        _time.sleep(0.4)  # widen the read->append window so the race is deterministic
        return out

    monkeypatch.setattr(kc, "known_fact_keys", _slow)
    results: list[int] = []

    def _worker() -> None:
        results.append(kc.append_facts([dict(row)], st))

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(results) == 1, "the same key must append exactly once under a race"
    assert len(kc.facts_path(st).read_text().splitlines()) == 1


# ── fix-wave 2 (whole-M1 closing sweep F1-F9, red-first) ─────────────────────────────


def _w2_row(sid: str, day: str, **over: object) -> dict:
    """A minimal well-formed derived-facts row for direct metric-input construction."""
    row: dict = {
        "facts_version": kc.FACTS_VERSION,
        "sid": sid,
        "day": day,
        "first_ts": f"{day}T10:00:00.000+00:00",
        "last_ts": f"{day}T11:00:00.000+00:00",
        "project": "proj-a",
        "events": {},
        "events_unattributed": {},
        "gate": {
            "runs": 0,
            "first_status": None,
            "pass": 0,
            "fail": 0,
            "failed_checks": {},
            "runs_noncheck": 0,
            "failed_checks_noncheck": {},
        },
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 0},
        "stop_causes": {},
        "death_classes": [],
        "concurrent": None,
        "concurrent_reason": None,
        "lines_total": 1,
        "lines_unclassified": 0,
        "unclassified_reasons": {},
    }
    row.update(over)
    return row


def test_derive_session_splits_noncheck_gate_fields(tmp_path: Path) -> None:
    """W2-F1: the derived row separates diagnostic --check gate runs from real
    completion runs — the taxonomy's population is the NON-check side only."""
    lines = [
        _line(
            "mix",
            "gate_run",
            "2026-08-18T10:00:00.000+00:00",
            status="failure",
            mode={"check": True, "lean": True, "systemic": False, "json": True},
            checks=[{"name": "docs", "outcome": "fail"}],
        ),
        _line(
            "mix",
            "gate_run",
            "2026-08-18T10:10:00.000+00:00",
            status="failure",
            mode={"check": False, "lean": False, "systemic": False, "json": True},
            checks=[{"name": "mypy", "outcome": "fail"}],
        ),
        _line(
            "mix",
            "gate_run",
            "2026-08-18T10:20:00.000+00:00",
            status="success",
            mode={"check": False, "lean": False, "systemic": False, "json": True},
            checks=[{"name": "mypy", "outcome": "pass"}],
        ),
    ]
    row = kc.derive_session(_session(tmp_path / "ev", "mix", lines))
    assert row is not None
    assert row["gate"]["runs"] == 3
    assert row["gate"]["runs_noncheck"] == 2
    assert row["gate"]["failed_checks"] == {"docs": 1, "mypy": 1}
    assert row["gate"]["failed_checks_noncheck"] == {"mypy": 1}
    assert row["gate"]["first_status"] == "failure", "L5: first NON-check run defines it"


def test_taxonomy_excludes_check_mode_gate_runs(tmp_path: Path) -> None:
    """W2-F1: a session whose gate runs are ALL --check (the Stop hook's --lean
    --check self-review) must never render the taxonomy — 'clean (0 failing checks
    over N runs)' from diagnostic runs is a fabrication."""
    lines = [
        _line(
            "chk",
            "gate_run",
            "2026-08-18T10:00:00.000+00:00",
            status="success",
            mode={"check": True, "lean": True, "systemic": False, "json": True},
            checks=[{"name": "ruff", "outcome": "pass"}],
        ),
        _line(
            "chk",
            "gate_run",
            "2026-08-18T10:30:00.000+00:00",
            status="success",
            mode={"check": True, "lean": True, "systemic": False, "json": True},
            checks=[{"name": "ruff", "outcome": "pass"}],
        ),
    ]
    row = kc.derive_session(_session(tmp_path / "ev", "chk", lines))
    assert row is not None
    metrics = kc.compute_metrics([row], holes=0)
    tax = metrics["gate_failure_taxonomy"]
    assert not tax.measurable, "check-only sessions are not taxonomy population"
    assert "clean" not in tax.cell
    assert "non-check" in tax.detail


def test_taxonomy_dashes_under_gate_run_attribution_floor() -> None:
    """W2-F1: when the gate_run family sits mostly in the unknown stream, the
    attributed sliver must not publish — dash with the attribution reason."""
    attributed = _w2_row(
        "s1",
        "2026-08-18",
        events={"gate_run": 1},
        gate={
            "runs": 1,
            "first_status": "failure",
            "pass": 0,
            "fail": 1,
            "failed_checks": {"mypy": 1},
            "runs_noncheck": 1,
            "failed_checks_noncheck": {"mypy": 1},
        },
    )
    unk = _w2_row(
        "unknown",
        "2026-08-18",
        project=None,
        events_unattributed={"gate_run": 40},
        concurrent_reason="unattributable-sid",
    )
    metrics = kc.compute_metrics([attributed, unk], holes=0)
    tax = metrics["gate_failure_taxonomy"]
    assert not tax.measurable, "1 attributed vs 40 unknown gate_runs is below the floor"
    assert "unattributable" in tax.detail
    assert "attribution floor" in tax.detail


def test_repopulated_metrics_publish_at_current_version(tmp_path: Path) -> None:
    """W2-F5 (updated by fix-wave 3's S5 bumps): a metric whose input population
    changed publishes at its CURRENT bumped version — never appending
    differently-defined points into an older version's files."""
    ev = tmp_path / "events"
    lines = [
        _line(
            "s1",
            "gate_run",
            "2026-08-18T10:00:00.000+00:00",
            status="failure",
            mode={"check": False, "lean": False, "systemic": False, "json": True},
            checks=[{"name": "mypy", "outcome": "fail"}],
        ),
        _line("s1", "stop_block", "2026-08-18T11:00:00.000+00:00", cause="run-record"),
        _line("s1", "stop_pass", "2026-08-18T12:00:00.000+00:00", outcome="clean"),
    ]
    _session(ev, "s1", lines)
    assert kc.daily(dt.date.today(), **_daily_args(tmp_path)) == 0
    st = tmp_path / "state"
    tax_ver = kc.registry()["gate_failure_taxonomy"]["version"]
    prem_ver = kc.registry()["premature_stop_rate"]["version"]
    assert kc.series_path("gate_failure_taxonomy", tax_ver, st).is_file()
    assert kc.series_path("premature_stop_rate", prem_ver, st).is_file()
    for old in range(1, tax_ver):
        assert not kc.series_path("gate_failure_taxonomy", old, st).exists()
    for old in range(1, prem_ver):
        assert not kc.series_path("premature_stop_rate", old, st).exists()


def test_era_filter_precedes_latest_per_sid_collapse(tmp_path: Path) -> None:
    """W2-F7: a transcript-era row that OUTRANKS its event-era sibling (T08 backfill)
    must not swallow the sid — the era filter runs BEFORE the collapse."""
    st = tmp_path / "state"
    ev_row = {"facts_version": 2, "sid": "s", "day": "2026-08-18", "lines_total": 1}
    tr_row = {
        "facts_version": 2,
        "sid": "s",
        "day": "2026-08-19",
        "era": "transcript",
        "lines_total": 5,
    }
    kc.append_facts([ev_row, tr_row], st)
    rows = kc.read_rows(state=st, event_era_only=True)
    assert [r["day"] for r in rows if r["sid"] == "s"] == ["2026-08-18"], (
        "the sid's event-era row must survive an outranking transcript sibling"
    )
    week = dt.date(2026, 8, 18).isocalendar()[:2]
    wrows = kc.read_week_rows(week, st, event_era_only=True)
    assert [r["day"] for r in wrows if r["sid"] == "s"] == ["2026-08-18"]
    # The era-blind default still serves the newest row — T08's report reads both eras.
    blind = kc.read_rows(state=st)
    assert [r["day"] for r in blind if r["sid"] == "s"] == ["2026-08-19"]


def test_daily_refuses_out_of_order_older_day(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W2-F4: an explicit --day older than the newest published series day would
    derive every alive file's CURRENT cumulative content under the old day and
    double-publish (append-only, unrepairable) — refuse, mutate nothing."""
    ev = tmp_path / "events"
    _session(ev, "s1", [_line("s1", "stop_pass", _TS, outcome="clean")])
    day_n = dt.date.today()
    assert kc.daily(day_n, **_daily_args(tmp_path)) == 0
    st = tmp_path / "state"
    log = tmp_path / "log.md"
    snapshot = {p: p.read_bytes() for p in st.rglob("*") if p.is_file()}
    log_before = log.read_bytes()

    rc = kc.daily(day_n - dt.timedelta(days=2), **_daily_args(tmp_path))
    assert rc != 0, "an out-of-order older day must refuse"
    err = capsys.readouterr().err
    assert day_n.isoformat() in err, "the refusal names the conflicting newest day"
    assert "kaizen_backfill" in err, "the refusal points historical backfill at its owner"
    after = {p: p.read_bytes() for p in st.rglob("*") if p.is_file()}
    assert after == snapshot, "the refused run must not mutate the state store"
    assert log.read_bytes() == log_before, "the refused run must not touch the log"


def test_coroner_holes_none_maps_to_transcripts_unreadable_dash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """W2-F3: a blind coroner (missing/unreadable transcripts dir) returns None —
    the collector dashes hole_count with the reason, never publishes a perfect 0."""
    import kaizen_coroner  # noqa: PLC0415 - same directory

    monkeypatch.setattr(kaizen_coroner, "holes", lambda *a, **k: None)
    holes, reason = kc._coroner_holes(dt.date.today(), tmp_path / "ev")
    assert holes is None
    assert reason == "transcripts unreadable"
    metrics = kc.compute_metrics([], holes=holes, holes_reason=reason)
    assert not metrics["hole_count"].measurable
    assert "transcripts unreadable" in metrics["hole_count"].detail


def test_bare_completion_gate_run_emits_noncheck_mode(tmp_path: Path) -> None:
    """W2-F9: the first_attempt_gate_pass population is satisfiable — a bare (no
    --check) completion gate emits ONE gate_run with mode.check false. Runs in a
    disposable shared clone so the bare gate's fixers can never touch the live
    tree; the events dir is a tmp dir, never the real store."""
    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(REPO), str(clone)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    events = tmp_path / "gate-events"
    env = dict(os.environ, KAIZEN_EVENTS_DIR=str(events), CLAUDE_SESSION_ID="w2-f9-bare")
    proc = subprocess.run(
        [
            sys.executable,
            str(clone / "scripts" / "final_gate.py"),
            "--lean",
            "--json",
            "--no-stage",
        ],
        cwd=str(clone),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode in (0, 1), proc.stderr[-2000:]
    rows = [
        json.loads(ln)
        for ln in (events / "w2-f9-bare.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    gate_rows = [r for r in rows if r.get("event") == "gate_run"]
    assert len(gate_rows) == 1, "exactly ONE gate_run per bare invocation"
    assert gate_rows[0]["mode"]["check"] is False, "a bare run is a completion run"
    assert gate_rows[0]["status"] in ("success", "failure")


# ── fix-wave 3 (root law + satellites, red-first) ────────────────────────────────────


def _v1_row(sid: str, day: str, **over: object) -> dict:
    """A FACTS_VERSION-1 row: NO events_unattributed, NO gate non-check split —
    the cross-version baseline of the root-law repro."""
    row = _w2_row(sid, day, **over)
    row["facts_version"] = 1
    row.pop("events_unattributed", None)
    row["gate"].pop("runs_noncheck", None)
    row["gate"].pop("failed_checks_noncheck", None)
    return row


def test_delta_row_field_absent_in_baseline_is_none_never_zero() -> None:
    """ROOT LAW (F1/F2/F6): a delta is only computable against a baseline that
    MEASURED the same field. A field the v1 predecessor never carried must come out
    None (unmeasurable), never cur-minus-0 (the full cumulative value as 'today')."""
    prev = _v1_row("s", "2026-08-18", events={"gate_run": 26}, lines_total=26)
    prev["gate"].update(runs=26, fail=26, failed_checks={"mypy": 6})
    cur = _w2_row(
        "s",
        "2026-08-19",
        events={"gate_run": 30},
        lines_total=30,
        gate={
            "runs": 30,
            "first_status": None,
            "pass": 0,
            "fail": 30,
            "failed_checks": {"mypy": 8},
            "runs_noncheck": 30,
            "failed_checks_noncheck": {"mypy": 8},
        },
    )
    delta = kc.delta_row(cur, prev)
    assert delta is not None
    assert delta["gate"]["runs"] == 4, "both-measured fields still delta normally"
    assert delta["gate"]["runs_noncheck"] is None, "absent-in-baseline scalar → None"
    assert delta["gate"]["failed_checks_noncheck"] is None, "absent-in-baseline map → None"
    assert delta["events_unattributed"] is None, "absent-in-baseline map → None"


def test_bump_day_taxonomy_goes_quiet_never_publishes_cumulative() -> None:
    """ROOT LAW, the exact round-3 probe: v1 predecessor + v3 current must make the
    taxonomy DASH for that sid on the bump day — never mypy=8 over runs_noncheck=30
    while the day's real runs delta is 4 (non-check ⊆ all, violated)."""
    prev = _v1_row("s", "2026-08-18", events={"gate_run": 26}, lines_total=26)
    prev["gate"].update(runs=26, fail=26, failed_checks={"mypy": 6})
    cur = _w2_row(
        "s",
        "2026-08-19",
        events={"gate_run": 30},
        lines_total=30,
        gate={
            "runs": 30,
            "first_status": None,
            "pass": 0,
            "fail": 30,
            "failed_checks": {"mypy": 8},
            "runs_noncheck": 30,
            "failed_checks_noncheck": {"mypy": 8},
        },
    )
    delta = kc.delta_row(cur, prev)
    assert delta is not None
    tax = kc.compute_metrics([delta], holes=0)["gate_failure_taxonomy"]
    assert not tax.measurable, "the bump day goes honestly quiet per-field"
    assert "mypy" not in tax.cell
    assert tax.denominator != 30
    assert "bump-day gap" in tax.detail


def test_runs_noncheck_exceeding_runs_is_unmeasurable_with_warn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ROOT LAW invariant: non-check ⊆ all — a row claiming runs_noncheck > runs is
    instrument-corrupt; warn and treat the non-check side as unmeasurable."""
    bad = _w2_row(
        "s",
        "2026-08-19",
        events={"gate_run": 4},
        gate={
            "runs": 4,
            "first_status": None,
            "pass": 0,
            "fail": 4,
            "failed_checks": {"mypy": 8},
            "runs_noncheck": 30,
            "failed_checks_noncheck": {"mypy": 8},
        },
    )
    tax = kc.compute_metrics([bad], holes=0)["gate_failure_taxonomy"]
    assert not tax.measurable
    err = capsys.readouterr().err
    assert "runs_noncheck" in err and "runs" in err


def test_attribution_guard_treats_none_unattributed_as_unmeasured() -> None:
    """ROOT LAW (F6): an events_unattributed=None delta row means the window's
    unattributed count is UNKNOWABLE — guarded metrics dash with the bump-day-gap
    reason instead of reading lifetime counts as window counts."""
    row = _w2_row(
        "s",
        "2026-08-19",
        events={"run_close": 2},
        runs={"opened": 2, "done": 2, "done_evidenced": 2, "blocked": 0, "rounds_max": 0},
    )
    row["events_unattributed"] = None
    m = kc.compute_metrics([row], holes=0)["rules_compliance"]
    assert not m.measurable
    assert "bump-day gap" in m.detail


def test_gate_guard_share_counts_noncheck_occurrences() -> None:
    """S7: the attribution guard's operands must come from the SAME population as
    the value it protects — non-check runs, not all gate_runs. 4 attributed
    gate_runs vs 8 unknown passes the old floor (33%), but only 1 is non-check
    (1/9 = 11%) — the taxonomy must dash."""
    attributed = _w2_row(
        "s1",
        "2026-08-18",
        events={"gate_run": 4},
        gate={
            "runs": 4,
            "first_status": "failure",
            "pass": 0,
            "fail": 4,
            "failed_checks": {"mypy": 4},
            "runs_noncheck": 1,
            "failed_checks_noncheck": {"mypy": 1},
        },
    )
    unk = _w2_row(
        "unknown",
        "2026-08-18",
        project=None,
        events_unattributed={"gate_run": 8},
        concurrent_reason="unattributable-sid",
    )
    tax = kc.compute_metrics([attributed, unk], holes=0)["gate_failure_taxonomy"]
    assert not tax.measurable
    assert "attribution floor" in tax.detail


def test_continuing_sessions_claim_keys_on_noncheck_runs() -> None:
    """S8: '(continuing sessions only)' keyed on unsplit gate.runs claims a
    continuing session where only diagnostic --check runs happened — the claim must
    be measured on runs_noncheck."""
    check_only = _w2_row(
        "s1",
        "2026-08-18",
        events={"gate_run": 2},
        gate={
            "runs": 2,
            "first_status": None,
            "pass": 2,
            "fail": 0,
            "failed_checks": {},
            "runs_noncheck": 0,
            "failed_checks_noncheck": {},
        },
    )
    m = kc.compute_metrics([check_only], holes=0)["first_attempt_gate_pass"]
    assert not m.measurable
    assert "continuing sessions only" not in m.detail, "check-only ≠ continuing"

    continuing = _w2_row(
        "s2",
        "2026-08-18",
        events={"gate_run": 2},
        gate={
            "runs": 2,
            "first_status": None,
            "pass": 2,
            "fail": 0,
            "failed_checks": {},
            "runs_noncheck": 2,
            "failed_checks_noncheck": {},
        },
    )
    m2 = kc.compute_metrics([continuing], holes=0)["first_attempt_gate_pass"]
    assert not m2.measurable
    assert "continuing sessions only" in m2.detail


def _publish_stub_day(tmp_path: Path, day: str) -> None:
    """Plant one published series day directly — the out-of-order guard's input."""
    p = kc.series_path("unclassified_rate", 99, tmp_path / "state")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"day": day, "metric": "unclassified_rate"}) + "\n")


def test_backpublish_refusal_names_the_escape_hatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """S4: the --day refusal must name KAIZEN_ALLOW_BACKPUBLISH so a wedged hourly
    cron is diagnosable from the log alone."""
    _publish_stub_day(tmp_path, dt.date.today().isoformat())
    rc = kc.daily(dt.date.today() - dt.timedelta(days=1), **_daily_args(tmp_path))
    assert rc == 1
    err = capsys.readouterr().err
    assert "REFUSED" in err
    assert "KAIZEN_ALLOW_BACKPUBLISH" in err


def test_backpublish_escape_hatch_downgrades_to_loud_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """S4: KAIZEN_ALLOW_BACKPUBLISH=1 downgrades the refusal to a warning and the
    run proceeds (rc 0) — the documented cron-unwedge path."""
    _publish_stub_day(tmp_path, dt.date.today().isoformat())
    monkeypatch.setenv("KAIZEN_ALLOW_BACKPUBLISH", "1")
    rc = kc.daily(dt.date.today() - dt.timedelta(days=1), **_daily_args(tmp_path))
    assert rc == 0
    err = capsys.readouterr().err
    assert "KAIZEN_ALLOW_BACKPUBLISH=1" in err


def test_backpublish_refusal_diagnoses_a_clock_jump(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """S4: a newest published day in the FUTURE relative to the requested day AND
    today is a clock-jump signature — the refusal must say so explicitly."""
    _publish_stub_day(tmp_path, (dt.date.today() + dt.timedelta(days=3)).isoformat())
    rc = kc.daily(dt.date.today() - dt.timedelta(days=1), **_daily_args(tmp_path))
    assert rc == 1
    err = capsys.readouterr().err
    assert "clock" in err.lower()
    assert "FUTURE" in err


# ── fix-wave 4 (windowed attribution + consumed-field gates, red-first) ──────────────


def test_windowed_unattributed_sums_per_day_deltas() -> None:
    """W4-1: the window's unattributed mass is the sum of the unknown accumulator's
    per-day DELTAS over the window days — cumulative rows subtract (delta seam),
    never re-count, and pre-window mass stays out."""
    d1 = _w2_row("unknown", "2026-08-10", events_unattributed={"round": 40})
    d2 = _w2_row("unknown", "2026-08-17", events_unattributed={"round": 45})
    d3 = _w2_row("unknown", "2026-08-18", events_unattributed={"round": 47})
    by_day = {"2026-08-10": d1, "2026-08-17": d2, "2026-08-18": d3}
    got = kc._windowed_unattributed(by_day, ("round",), ["2026-08-17", "2026-08-18"])
    assert got == (7, None), "45-40 on 08-17 plus 47-45 on 08-18 — never the cumulative 47"
    assert kc._windowed_unattributed(by_day, ("round",), ["2026-08-19", "2026-08-20"]) == (0, None)
    assert kc._windowed_unattributed({}, ("round",), ["2026-08-18"]) == (0, None), (
        "a fresh store measured nothing unattributable — a knowable 0"
    )


def test_windowed_unattributed_pre_v3_rows_are_unknowable() -> None:
    """W4-1 root law + W5-2: an in-window unknown row without the
    events_unattributed field (a live v1 row), or one whose delta has no
    same-field baseline, makes the window's count None — absent ≠ 0 — and the
    verdict carries WHICH cause."""
    v1 = _w2_row("unknown", "2026-08-18")
    v1["facts_version"] = 1
    v1.pop("events_unattributed", None)
    assert kc._windowed_unattributed({"2026-08-18": v1}, ("round",), ["2026-08-18"]) == (
        None,
        kc.UNATTR_PRE_V3,
    )
    # A measured current row over an absent-field v1 baseline: bump-day gap → None.
    v3 = _w2_row("unknown", "2026-08-19", events_unattributed={"round": 50})
    by_day = {"2026-08-18": v1, "2026-08-19": v3}
    assert kc._windowed_unattributed(by_day, ("round",), ["2026-08-19"]) == (
        None,
        kc.UNATTR_BUMP_GAP,
    )


def test_windowed_unattributed_shrink_and_bootstrap_carry_their_causes() -> None:
    """W5-2 (#2) + W5-3 (#4): a shrunk accumulator reports the SHRINK cause (the
    wave-4 seam returned a bare None and every consumer printed 'pre-v3 rows in
    window'); a first-ever in-window derivation carrying family mass reports the
    BOOTSTRAP cause; a first-ever row with ZERO family mass dumped nothing for
    that family — a knowable 0."""
    base = _w2_row("unknown", "2026-08-01", events_unattributed={"round": 50})
    shrunk = _w2_row("unknown", "2026-08-18", events_unattributed={"round": 40})
    assert kc._windowed_unattributed(
        {"2026-08-01": base, "2026-08-18": shrunk}, ("round",), ["2026-08-18"]
    ) == (None, kc.UNATTR_SHRUNK)
    boot = _w2_row("unknown", "2026-08-18", events_unattributed={"round": 40})
    assert kc._windowed_unattributed({"2026-08-18": boot}, ("round",), ["2026-08-18"]) == (
        None,
        kc.UNATTR_BOOTSTRAP,
    )
    no_mass = _w2_row("unknown", "2026-08-18", events_unattributed={"gate_run": 9})
    assert kc._windowed_unattributed({"2026-08-18": no_mass}, ("round",), ["2026-08-18"]) == (
        0,
        None,
    ), "family-scoped: a bootstrap row with zero round mass is a knowable 0"


def test_first_attempt_bump_gap_rows_are_counted_and_noted() -> None:
    """W4-2: the v3 formula promises bump-gap accounting — a row outside the
    population whose non-check split was measured with no same-field baseline
    (runs_noncheck None, root law) is counted into gaps and the note appended."""
    measured = _w2_row(
        "s1",
        "2026-08-18",
        events={"gate_run": 1},
        gate={
            "runs": 1,
            "first_status": "success",
            "pass": 1,
            "fail": 0,
            "failed_checks": {},
            "runs_noncheck": 1,
            "failed_checks_noncheck": {},
        },
    )
    gap = _w2_row("s2", "2026-08-19", events={"gate_run": 4})
    gap["gate"] = {
        "runs": 4,
        "first_status": None,
        "pass": 0,
        "fail": 4,
        "failed_checks": {"mypy": 1},
        "runs_noncheck": None,
        "failed_checks_noncheck": None,
    }
    m = kc.compute_metrics([measured, gap], holes=0)["first_attempt_gate_pass"]
    assert m.measurable
    assert (m.numerator, m.denominator) == (1, 1)
    # W5-4 (#7) wording: the row was never IN the population, so the note must
    # not claim an exclusion — it is unmeasurable this window.
    assert "1 row(s) unmeasurable this window — bump-day gap" in m.detail
    assert "excluded" not in m.detail


def test_first_attempt_consumed_row_is_out_of_population_not_a_gap() -> None:
    """W5-4 (#6): a delta row whose first_status was NULLED because the
    predecessor already recorded it (first attempt CONSUMED) is out of the
    population BY DESIGN — even when its non-check split gapped (runs_noncheck
    None, a bump day), it must NOT count as a first_attempt bump-day gap. The
    delta row carries the distinction as the first_status_consumed marker."""
    prev = _w2_row(
        "s1",
        "2026-08-17",
        events={"gate_run": 1},
        gate={
            "runs": 1,
            "first_status": "success",
            "pass": 1,
            "fail": 0,
            "failed_checks": {},
            # a v2-shaped predecessor: no non-check split measured
        },
    )
    prev["gate"].pop("runs_noncheck", None)
    prev["gate"].pop("failed_checks_noncheck", None)
    cur = _w2_row(
        "s1",
        "2026-08-18",
        events={"gate_run": 3},
        gate={
            "runs": 3,
            "first_status": "success",
            "pass": 3,
            "fail": 0,
            "failed_checks": {},
            "runs_noncheck": 3,
            "failed_checks_noncheck": {},
        },
    )
    delta = kc.delta_row(cur, prev)
    assert delta is not None
    assert delta["gate"]["first_status"] is None
    assert delta["gate"]["first_status_consumed"] is True, (
        "the suppression must MARK the row consumed — root-law-safe distinction"
    )
    assert delta["gate"]["runs_noncheck"] is None, "the bump-day gap combo is real here"
    m = kc.compute_metrics([delta], holes=0)["first_attempt_gate_pass"]
    assert not m.measurable  # no first attempt this window — honest dash
    assert "bump-day gap" not in m.detail, (
        "a consumed first attempt is out-of-population, never a bump-day gap"
    )


def test_rules_compliance_survives_events_map_gap_it_never_consumes() -> None:
    """W4-4: rules_compliance reads runs.* baselines only — an events-map bump-day
    gap must not drop its fully-measured row; terminator_spam (which consumes the
    events map) keeps the events gate and dashes with the gap noted."""
    row = _w2_row(
        "s1",
        "2026-08-19",
        runs={"opened": 2, "done": 2, "done_evidenced": 1, "blocked": 0, "rounds_max": 0},
    )
    row["events"] = None  # root-law gap on a map rules_compliance never reads
    metrics = kc.compute_metrics([row], holes=0)
    rc = metrics["rules_compliance"]
    assert rc.measurable, "an unconsumed events-map gap must not drop the row"
    assert (rc.numerator, rc.denominator) == (1, 2)
    ts = metrics["terminator_spam"]
    assert not ts.measurable
    assert "bump-day gap" in ts.detail


def test_no_closures_message_counts_blocks_on_excluded_rows() -> None:
    """W4-5: blocks OBSERVED on gap-excluded rows must appear in the 'no closures'
    message — '(0 terminator block(s) seen)' over a store that saw 2 is fabricated.
    The metric population stays gap-filtered; only the message counts all rows."""
    gap = _w2_row("s1", "2026-08-19", events={"final_block_emitted": 2})
    gap["runs"] = {
        "opened": None,
        "done": None,
        "done_evidenced": None,
        "blocked": None,
        "rounds_max": 0,
    }
    ts = kc.compute_metrics([gap], holes=0)["terminator_spam"]
    assert not ts.measurable
    assert "2 terminator block(s) seen" in ts.detail


def test_fact_keys_are_era_aware(tmp_path: Path) -> None:
    """W4-3: TRANSCRIPT_FACTS_VERSION (1) collides numerically with live v1 EVENT
    rows — an era-blind (sid, version, day) key let the event row silently mask the
    transcript derivation at the same triple. The key carries the era."""
    st = tmp_path / "state"
    event_v1 = {
        "facts_version": 1,
        "sid": "aaaa1111",
        "day": "2026-06-05",
        "events": {},
        "lines_total": 1,
    }
    assert kc.append_facts([event_v1], st) == 1
    transcript = {
        "facts_version": 1,
        "era": "transcript",
        "sid": "aaaa1111",
        "day": "2026-06-05",
        "events": DASH,
        "lines_total": 5,
    }
    assert kc.append_facts([transcript], st) == 1, (
        "a v1 EVENT row must never mask the transcript derivation at (sid, day)"
    )
    assert kc.append_facts([dict(transcript)], st) == 0, "same-era re-append stays a no-op"
    keys = kc.known_fact_keys(st)
    assert ("aaaa1111", 1, "2026-06-05", "event") in keys
    assert ("aaaa1111", 1, "2026-06-05", "transcript") in keys


# ── fix-wave 5 (W5: the weekly seam reads windowed delta rows, red-first) ────────────


def test_window_delta_rows_are_in_window_growth_per_sid(tmp_path: Path) -> None:
    """W5-1: every sid's in-window rows are delta'd against its nearest earlier
    row — a lifetime session contributes only its in-window growth, and a row
    with no predecessor is its own delta."""
    st = tmp_path / "state"
    pre = _w2_row("s1", "2026-08-10", events={"round": 60})
    cur = _w2_row("s1", "2026-08-18", events={"round": 62})
    fresh = _w2_row("s2", "2026-08-18", events={"round": 2})
    kc.append_facts([pre, cur, fresh], st)
    deltas = kc.window_delta_rows(["2026-08-17", "2026-08-18"], st)
    by_sid = {r["sid"]: r for r in deltas}
    assert set(by_sid) == {"s1", "s2"}, "only in-window days produce delta rows"
    assert by_sid["s1"]["events"] == {"round": 2}, "60 lifetime rounds are not the window's"
    assert by_sid["s1"]["delta_of"] == "2026-08-10"
    assert by_sid["s2"]["events"] == {"round": 2}
    assert by_sid["s2"]["delta_of"] is None


def test_weekly_blocks_seen_counts_window_growth_not_lifetime(tmp_path: Path) -> None:
    """W5-5 (#8): fed by the window's delta rows, the 'no closures' message counts
    the WINDOW's terminator blocks — a lifetime cumulative 7 must not appear
    inside a week-scoped message when the week's growth is 2."""
    st = tmp_path / "state"
    pre = _w2_row("s1", "2026-08-10", events={"final_block_emitted": 5})
    cur = _w2_row("s1", "2026-08-18", events={"final_block_emitted": 7})
    kc.append_facts([pre, cur], st)
    deltas = kc.window_delta_rows(["2026-08-17", "2026-08-18"], st)
    ts = kc.compute_metrics(deltas, holes=0)["terminator_spam"]
    assert not ts.measurable
    assert "2 terminator block(s) seen" in ts.detail, (
        "the week-scoped message must count the week's growth, never lifetime mass"
    )


def test_daily_weekly_cells_read_window_deltas_not_cumulative_rows(tmp_path: Path) -> None:
    """W5-5 (falls out of W5-1): daily()'s weekly call must consume the ISO week's
    day-scoped delta rows — a session whose first attempt was consumed in an
    EARLIER week must not be re-counted as this week's first-attempt population
    (the cumulative week row carries the lifetime first_status forever, so the old
    read published 100% every week the file grew)."""
    st = tmp_path / "state"
    prev_week_day = (dt.date.today() - dt.timedelta(days=8)).isoformat()
    pre = _w2_row(
        "s1",
        prev_week_day,
        events={"gate_run": 1},
        gate={
            "runs": 1,
            "first_status": "success",
            "pass": 1,
            "fail": 0,
            "failed_checks": {},
            "runs_noncheck": 1,
            "failed_checks_noncheck": {},
        },
    )
    cur = _w2_row(
        "s1",
        dt.date.today().isoformat(),
        events={"gate_run": 2},
        gate={
            "runs": 2,
            "first_status": "success",
            "pass": 2,
            "fail": 0,
            "failed_checks": {},
            "runs_noncheck": 2,
            "failed_checks_noncheck": {},
        },
    )
    kc.append_facts([pre, cur], st)
    args = _daily_args(tmp_path)
    args["events"].mkdir(exist_ok=True)
    assert kc.daily(dt.date.today(), **args) == 0
    row_line = next(
        ln
        for ln in args["log_paths"][0].read_text(encoding="utf-8").splitlines()
        if ln.startswith(f"| {dt.date.today().isoformat()}")
    )
    cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
    assert cells[1] == DASH, (
        "the first attempt was consumed LAST week — this week's cell must not "
        "re-count the cumulative row's lifetime first_status"
    )


# ── fix-wave 6 (W6-1: the single-source law — weekly cells read the DAY SERIES) ──────


def _plant_point(st: Path, metric: str, version: int, day: str, **fields: object) -> None:
    """Plant one published day point directly in the metric's series file."""
    p = kc.series_path(metric, version, st)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"day": day, "metric": metric, "version": version, **fields}
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _full_reg() -> dict:
    import kaizen_outcomes  # noqa: PLC0415

    return kaizen_outcomes.registry()


def test_weekly_cells_aggregate_the_published_day_series(tmp_path: Path) -> None:
    """W6-1: mechanical weekly cells aggregate THE PUBLISHED DAY SERIES — ratio
    cells sum the week's day numerators/denominators (per-session shares can
    never dilute into per-row shares), the death cell sums occurrences and merges
    the day class maps. The rounds cell is the single-source law's ONE carve-out
    (W8-1): a point-in-time per-session quantity recomputed latest-per-sid over
    the week's delta rows — anonymous day points cannot per-session-deduplicate
    a multi-day session."""
    st = tmp_path / "state"
    reg = _full_reg()
    day = dt.date(2026, 8, 18)  # Tuesday; the elapsed week is the 17th..18th
    fa_v = int(reg["first_attempt_gate_pass"]["version"])
    _plant_point(st, "first_attempt_gate_pass", fa_v, "2026-08-17", numerator=2, denominator=2)
    _plant_point(st, "first_attempt_gate_pass", fa_v, "2026-08-18", numerator=1, denominator=3)
    do_v = int(reg["death_occurrences"]["version"])
    dc_v = int(reg["death_classes"]["version"])
    _plant_point(st, "death_occurrences", do_v, "2026-08-17", value=2, numerator=2)
    _plant_point(st, "death_occurrences", do_v, "2026-08-18", value=1, numerator=1)
    _plant_point(st, "death_classes", dc_v, "2026-08-17", value={"rate_limit": 1, "oom": 1})
    _plant_point(st, "death_classes", dc_v, "2026-08-18", value={"oom": 1})
    # W8-1: the rounds cell recomputes from the week's delta rows (latest-per-
    # sid), never from day points — sessions born and grown on week days
    kc.append_facts(
        [
            _week_row("sA", dt.date(2026, 8, 17), 6),
            _week_row("sB", dt.date(2026, 8, 18), 9),
        ],
        st,
    )
    cells = kc.log_cells(day, reg, state=st)
    assert cells[1] == "60% (3/5)", "ratio cells sum the week's day num/den"
    assert cells[2] == "3 occ / 2 cls", "the death cell is the week's real occ/cls"
    assert cells[4] == "7.5 (n=2)", (
        "the rounds cell weights each session once at its latest rounds_max (W8-1)"
    )


def test_weekly_cells_dash_when_the_series_has_no_published_days(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W6-1 (the round-6 probes): NO row recompute exists — a store full of
    lifetime rows (rounds_max=9, two lifetime death classes) with NO published
    day points this week renders — for every mechanical cell: the 9.0 (n=1)
    zero-growth rounds cell and the '0 occ / 2 cls' mixed-semantics shape are
    structurally dead."""
    st = tmp_path / "state"
    row = _w2_row(
        "s1",
        "2026-08-18",
        events={"round": 0},
        runs={"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 9},
        death_classes=["rate_limit", "oom"],
    )
    kc.append_facts([row], st)
    cells = kc.log_cells(dt.date(2026, 8, 18), _full_reg(), state=st)
    assert cells[1] == DASH and cells[2] == DASH and cells[4] == DASH, (
        "store rows must be unreachable from a weekly cell — series or dash"
    )
    err = capsys.readouterr().err
    assert "no published days this week" in err


def test_weekly_cells_read_only_the_current_registry_version(tmp_path: Path) -> None:
    """W6-1: a retired version's series file is history — the weekly cell reads
    only the CURRENT registry version's file."""
    st = tmp_path / "state"
    _plant_point(st, "review_rounds", 1, "2026-08-18", value=9.0, numerator=9, denominator=1)
    cells = kc.log_cells(dt.date(2026, 8, 18), _full_reg(), state=st)
    assert cells[4] == DASH, "a stale-version series file must not feed the cell"


def test_delta_row_death_classes_is_the_new_suffix() -> None:
    """W6-1: death_classes is DELTA'd — the in-order suffix beyond the
    predecessor's list, never the lifetime list; a shorter list is a shrink
    (publish nothing); a baseline that never measured the list is a root-law
    None."""
    prev = _w2_row("s", "2026-08-17", events={"death": 2}, death_classes=["a", "b"])
    cur = _w2_row("s", "2026-08-18", events={"death": 3}, death_classes=["a", "b", "c"])
    d = kc.delta_row(cur, prev)
    assert d is not None and d["death_classes"] == ["c"], "only the day's NEW classes"
    shrunk = _w2_row("s", "2026-08-18", events={"death": 2}, death_classes=["a"])
    assert kc.delta_row(shrunk, prev) is None, "a shorter class list is a shrink"
    legacy_prev = _w2_row("s", "2026-08-17", events={"death": 2})
    legacy_prev.pop("death_classes")
    d2 = kc.delta_row(cur, legacy_prev)
    assert d2 is not None and d2["death_classes"] is None, (
        "no same-field baseline — root-law None, never the lifetime list"
    )


def test_death_pair_measures_only_with_coroner_evidence() -> None:
    """W6-1: the death pair publishes a day point only when the day's rows carry
    coroner evidence (a death or session_end event) — a 0 without evidence would
    fabricate a coroner run (M9, day-scoped); a session_end-backed zero is a
    genuine measured 0."""
    quiet = _w2_row("s", "2026-08-18", events={"stop_pass": 1}, death_classes=[])
    m = kc.compute_metrics([quiet], holes=0)
    assert not m["death_occurrences"].measurable and not m["death_classes"].measurable
    assert "coroner" in m["death_occurrences"].detail
    dead = _w2_row(
        "s",
        "2026-08-18",
        events={"death": 2, "session_end": 1},
        death_classes=["rate_limit", "oom"],
    )
    m2 = kc.compute_metrics([dead], holes=0)
    assert m2["death_occurrences"].measurable and m2["death_occurrences"].cell == "2"
    assert m2["death_classes"].value == {"rate_limit": 1, "oom": 1}
    closed = _w2_row("s", "2026-08-18", events={"session_end": 1}, death_classes=[])
    m3 = kc.compute_metrics([closed], holes=0)
    assert m3["death_occurrences"].measurable and m3["death_occurrences"].cell == "0", (
        "a session_end-backed zero is a genuine coroner-backed 0"
    )


def test_death_classes_accepts_v1_scalar_death_class() -> None:
    """W2-F6 carried forward into the day metric: a FACTS_VERSION-1 row carries a
    SCALAR death_class — the class distribution must see it."""
    legacy = {
        "facts_version": 1,
        "sid": "legacy",
        "day": "2026-08-18",
        "events": {"death": 2},
        "death_class": "rate_limit",
        "runs": {},
        "stop_causes": {},
        "gate": {"runs": 0, "first_status": None, "pass": 0, "fail": 0, "failed_checks": {}},
        "lines_total": 4,
        "lines_unclassified": 0,
        "unclassified_reasons": {},
    }
    m = kc.compute_metrics([legacy], holes=0)
    assert m["death_occurrences"].cell == "2"
    assert m["death_classes"].value == {"rate_limit": 1}


def test_daily_weekly_row_is_fed_by_the_day_series(tmp_path: Path) -> None:
    """W6-1 end to end: daily() publishes the day series first and the weekly log
    row aggregates THOSE points — the golden corpus's death lands in the log row
    as the week's real occ/cls."""
    rc, _, st, log = _green_daily(tmp_path, dt.date.today())
    assert rc == 0
    do_v = int(_full_reg()["death_occurrences"]["version"])
    assert kc.series_path("death_occurrences", do_v, st).is_file(), (
        "the death pair publishes day points"
    )
    text = log.read_text(encoding="utf-8")
    row_line = next(
        ln for ln in text.splitlines() if ln.startswith(f"| {dt.date.today().isoformat()}")
    )
    cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
    assert cells[2] == "1 occ / 1 cls", "golden-bravo's rate_limit death, from the series"


# ── fix-wave 7 (W7: day-scoped day points, split weeks, the death pair contract) ──────


def _this_week_monday() -> dt.date:
    today = dt.date.today()
    return today - dt.timedelta(days=today.isoweekday() - 1)


def _week_row(sid: str, day: dt.date, rounds: int) -> dict:
    return _w2_row(
        sid,
        day.isoformat(),
        first_ts=f"{day.isoformat()}T12:00:00.000+00:00",
        last_ts=f"{day.isoformat()}T13:00:00.000+00:00",
        events={"round": rounds},
        runs={"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": rounds},
    )


def test_outcome_day_points_are_day_scoped_not_windowed(tmp_path: Path) -> None:
    """W7-1 (the round-7 probe): the PUBLISHED review_rounds day point is
    DAY-scoped — that day's delta rows only. One session with round growth on one
    day, published across seven daily passes, is ONE day point and a weekly cell
    of 3.0 (n=1) — never seven copies of a trailing-window value summing to
    3.0 (n=7) (each session re-counted once per derivation-day residency)."""
    st = tmp_path / "state"
    monday = _this_week_monday()
    kc.append_facts([_week_row("s1", monday, 3)], st)
    for k in range(7):
        kc._publish_outcome_series((monday + dt.timedelta(days=k)).isoformat(), st)
    reg = _full_reg()
    rr_path = kc.series_path("review_rounds", int(reg["review_rounds"]["version"]), st)
    assert rr_path.is_file(), "the growth day must publish its day point"
    points = [json.loads(ln) for ln in rr_path.read_text().splitlines()]
    assert [p["day"] for p in points] == [monday.isoformat()], (
        "only the day whose delta rows carry the growth publishes — a "
        "trailing-window value must never publish as six more day points"
    )
    cells = kc.log_cells(monday + dt.timedelta(days=6), reg, state=st)
    assert cells[4] == "3.0 (n=1)", "one session, one day point — never (n=7)"


def test_outcome_day_points_weekly_mean_is_per_session(tmp_path: Path) -> None:
    """W7-1 (the A+B probe): session A (rounds_max 3, grew Monday) and session B
    (rounds_max 9, grew Tuesday) weekly-mean to 6.0 (n=2) — the day-scoped points
    weight each session once, never by its window residency."""
    st = tmp_path / "state"
    monday = _this_week_monday()
    kc.append_facts(
        [_week_row("a", monday, 3), _week_row("b", monday + dt.timedelta(days=1), 9)], st
    )
    for k in range(7):
        kc._publish_outcome_series((monday + dt.timedelta(days=k)).isoformat(), st)
    cells = kc.log_cells(monday + dt.timedelta(days=6), _full_reg(), state=st)
    assert cells[4] == "6.0 (n=2)", "the weekly mean weights each session once"


def test_stops_day_points_are_day_scoped(tmp_path: Path) -> None:
    """W7-1: the stops pair's published day points are day-scoped too — a
    one-day session must land exactly one premature_stop day point across seven
    daily passes."""
    st = tmp_path / "state"
    monday = _this_week_monday()
    row = _w2_row(
        "s1",
        monday.isoformat(),
        first_ts=f"{monday.isoformat()}T12:00:00.000+00:00",
        events={"stop_pass": 2, "stop_block": 1},
        stop_causes={"run-record": 1},
    )
    kc.append_facts([row], st)
    for k in range(7):
        kc._publish_outcome_series((monday + dt.timedelta(days=k)).isoformat(), st)
    reg = _full_reg()
    ps_path = kc.series_path("premature_stop", int(reg["premature_stop"]["version"]), st)
    assert ps_path.is_file()
    days = [json.loads(ln)["day"] for ln in ps_path.read_text().splitlines()]
    assert days == [monday.isoformat()], (
        "a windowed value published under seven day stamps is seven overlapping "
        "windows — the day point is the day's rows only"
    )


def test_weekly_cells_annotate_a_mid_week_definition_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W7-2: a mid-week registry version bump must not silently truncate the week
    — the cell aggregates ONLY current-definition points, carries a * marker, and
    the stderr note states k of N week days at the current definition. (Vehicle:
    the gate metric — the rounds cell recomputes from store rows since W8-1 and
    cannot mix versions.)"""
    st = tmp_path / "state"
    reg = _full_reg()
    fa_v = int(reg["first_attempt_gate_pass"]["version"])
    for d in ("2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21"):
        _plant_point(st, "first_attempt_gate_pass", fa_v - 1, d, numerator=1, denominator=2)
    _plant_point(st, "first_attempt_gate_pass", fa_v, "2026-08-22", numerator=2, denominator=2)
    _plant_point(st, "first_attempt_gate_pass", fa_v, "2026-08-23", numerator=2, denominator=2)
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[1] == "100% (4/4)*", "never a silent 100% (4/4) over a truncated week"
    err = capsys.readouterr().err
    assert "2 of 7 week day(s) at the current definition" in err
    assert "definition changed mid-week" in err
    assert "covers only its metric's current-definition days" in err


def test_weekly_cell_dash_names_the_definition_change_when_no_current_days(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W7-2: when the week holds ONLY prior-definition day points the dash reason
    says the definition changed — never the generic no-published-days claim."""
    st = tmp_path / "state"
    reg = _full_reg()
    fa_v = int(reg["first_attempt_gate_pass"]["version"])
    for d in ("2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20"):
        _plant_point(st, "first_attempt_gate_pass", fa_v - 1, d, numerator=1, denominator=2)
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[1] == DASH
    err = capsys.readouterr().err
    assert "definition changed this week; no days published at the current definition yet" in err


def test_death_cell_dashes_when_the_pair_is_one_sided(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W7-3: measurability requires BOTH halves — occurrence day points with NO
    class day points (and vice versa) dash with the pair-contract reason, never
    'N occ / 0 cls'."""
    st = tmp_path / "state"
    reg = _full_reg()
    do_v = int(reg["death_occurrences"]["version"])
    _plant_point(st, "death_occurrences", do_v, "2026-08-17", value=14, numerator=14)
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[2] == DASH, "occurrences without class points is one-sided — dash"
    err = capsys.readouterr().err
    assert "BOTH halves" in err
    st2 = tmp_path / "state2"
    dc_v = int(reg["death_classes"]["version"])
    _plant_point(st2, "death_classes", dc_v, "2026-08-17", value={"oom": 1})
    cells2 = kc.log_cells(dt.date(2026, 8, 23), reg, state=st2)
    assert cells2[2] == DASH, "class points without occurrences is one-sided — dash"
    assert "BOTH halves" in capsys.readouterr().err


def test_death_cell_dash_names_the_coroner_quiet_cause(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W7-6: the coroner-quiet week's dash distinguishes its cause via the
    whole-store universe signal — never run · series file missing at the current
    version · every week day gapped/unpublished."""
    reg = _full_reg()
    day = dt.date(2026, 8, 23)
    # (a) nothing anywhere: the coroner has never run
    kc.log_cells(day, reg, state=tmp_path / "a")
    assert "the coroner has never run" in capsys.readouterr().err
    # (b) coroner evidence in the store, but no current-version series file
    st_b = tmp_path / "b"
    kc.append_facts([_w2_row("s", "2026-08-18", events={"session_end": 1})], st_b)
    kc.log_cells(day, reg, state=st_b)
    err_b = capsys.readouterr().err
    assert "missing at the current version" in err_b
    assert "the coroner has never run" not in err_b
    # (c) evidence + a current-version file whose points all fall outside the week
    st_c = tmp_path / "c"
    kc.append_facts([_w2_row("s", "2026-08-18", events={"session_end": 1})], st_c)
    do_v = int(reg["death_occurrences"]["version"])
    _plant_point(st_c, "death_occurrences", do_v, "2026-08-10", value=1, numerator=1)
    _plant_point(
        st_c, "death_classes", int(reg["death_classes"]["version"]), "2026-08-10", value={}
    )
    kc.log_cells(day, reg, state=st_c)
    err_c = capsys.readouterr().err
    assert "every week day gapped" in err_c
    assert "missing at the current version" not in err_c


# ── fix-wave 8 (W8: per-session rounds cell, per-half split weeks) ───────────────────


def test_rounds_weekly_cell_weights_a_multiday_session_once(tmp_path: Path) -> None:
    """W8-1 (the round-8 probe): one session whose rounds grow 3 → 6 → 9 across
    three week days publishes three honest day points, but the WEEKLY cell is
    9.0 (n=1) — the session's latest point-in-time rounds_max, once — never
    6.0 (n=3) (its partial values summed, its residency days re-counted)."""
    st = tmp_path / "state"
    monday = _this_week_monday()
    kc.append_facts(
        [
            _week_row("s1", monday, 3),
            _week_row("s1", monday + dt.timedelta(days=2), 6),
            _week_row("s1", monday + dt.timedelta(days=4), 9),
        ],
        st,
    )
    for k in range(7):
        kc._publish_outcome_series((monday + dt.timedelta(days=k)).isoformat(), st)
    cells = kc.log_cells(monday + dt.timedelta(days=6), _full_reg(), state=st)
    assert cells[4] == "9.0 (n=1)", (
        "a point-in-time per-session quantity must weight each session once at its "
        "latest value — never once per growth day with partial values summed"
    )


def test_death_cell_one_sided_version_bump_is_never_bare(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W8-3: a mid-week version bump on ONE death-pair half (classes at v2,
    occurrences still v1) must surface as a split week — annotated or dashed,
    never a bare cell mixing a fully-covered occurrence sum with a truncated
    class merge."""
    st = tmp_path / "state"
    reg = _full_reg()
    do_v = int(reg["death_occurrences"]["version"])
    dc_v = int(reg["death_classes"]["version"])
    week = ["2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21", "2026-08-22"]
    for d in week:
        _plant_point(st, "death_occurrences", do_v, d, value=2, numerator=2)
    for d in week[:5]:
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"cls-{d[-2:]}": 1})
    _plant_point(st, "death_classes", dc_v, week[5], value={"oom": 1})
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[2] != "12 occ / 1 cls", (
        "five days of class breadth measured under the previous definition must "
        "never vanish under a bare, fully-measured-looking cell"
    )
    assert cells[2] == DASH or cells[2].endswith("*")
    err = capsys.readouterr().err
    assert "definition" in err


# ── fix-wave 9 (W9: the carve-out cell speaks; split-week truth in every branch) ─────


def test_rounds_weekly_cell_carries_its_detail_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W9-2: the recomputed rounds cell must not be the one bare number — its
    honesty annotations (attribution share, bootstrap exclusions, smear) are
    printed alongside the row, never silently folded."""
    st = tmp_path / "state"
    monday = _this_week_monday()
    kc.append_facts([_week_row("s1", monday, 3)], st)
    cells = kc.log_cells(monday + dt.timedelta(days=6), _full_reg(), state=st)
    assert cells[4] == "3.0 (n=1)"
    err = capsys.readouterr().err
    assert "Review rounds /plan" in err
    assert "attribution share" in err, "the guard's share must ride with the cell"


def test_death_cell_zero_current_days_names_the_definition_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W9-3: a class half bumped mid-week with ZERO current-version days must
    dash naming the definition change — six previous-definition class points
    exist, so 'no class day points' (the pair contract) is a false claim."""
    st = tmp_path / "state"
    reg = _full_reg()
    do_v = int(reg["death_occurrences"]["version"])
    dc_v = int(reg["death_classes"]["version"])
    week = ["2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21", "2026-08-22"]
    for d in week:
        _plant_point(st, "death_occurrences", do_v, d, value=2, numerator=2)
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"cls-{d[-2:]}": 1})
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[2] == DASH
    err = capsys.readouterr().err
    assert "definition changed this week" in err
    assert "no class day points" not in err, (
        "six class points exist under the previous definition — the pair-contract "
        "claim would be false"
    )


def test_death_cell_split_week_note_states_both_halves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W9-5: the split-week note for a PAIR states each half's current-definition
    day count — '1 of 7' beside a 6-day occurrence sum misdescribes which half
    is truncated."""
    st = tmp_path / "state"
    reg = _full_reg()
    do_v = int(reg["death_occurrences"]["version"])
    dc_v = int(reg["death_classes"]["version"])
    week = ["2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21", "2026-08-22"]
    for d in week:
        _plant_point(st, "death_occurrences", do_v, d, value=2, numerator=2)
    for d in week[:5]:
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"cls-{d[-2:]}": 1})
    _plant_point(st, "death_classes", dc_v, week[5], value={"oom": 1})
    kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    err = capsys.readouterr().err
    assert "death_occurrences 6/7" in err
    assert "death_classes 1/7" in err


# ── fix-wave 10 (W10: the true one-sided cause; disjoint halves never mix) ───────────


def test_death_cell_unpublished_half_names_the_pair_contract_not_the_split(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W10-1: a half that published NOTHING this week (no version bump — no
    orphan days) is a pair-contract gap; the split-week reason is the true cause
    only when the empty half's emptiness is bump-caused. W9-3's intersection
    precedence claimed 'no days published at the current definition yet' while
    the other half had three current-definition days."""
    st = tmp_path / "state"
    reg = _full_reg()
    dc_v = int(reg["death_classes"]["version"])
    for d in ("2026-08-17", "2026-08-18", "2026-08-19"):
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"cls-{d[-2:]}": 1})
    for d in ("2026-08-20", "2026-08-21", "2026-08-22"):
        _plant_point(st, "death_classes", dc_v, d, value={f"cls-{d[-2:]}": 1})
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[2] == DASH
    err = capsys.readouterr().err
    assert "no occurrence day points" in err, (
        "the occurrence half never published — that is the actionable cause"
    )
    assert "no days published at the current definition yet" not in err, (
        "three class days ARE at the current definition — the split claim is false"
    )


def test_death_cell_disjoint_current_halves_dash_never_mix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W10-2: both halves bumped on different days — occurrences current
    Mon-Wed, classes current Thu-Sat — share NO current-definition day; pairing
    an occurrence sum with a class set from disjoint definitions is the exact
    fabrication the pair contract exists to prevent. Dash, never '6 occ / 2 cls*'
    annotated as covering 0 of 7 days."""
    st = tmp_path / "state"
    reg = _full_reg()
    do_v = int(reg["death_occurrences"]["version"])
    dc_v = int(reg["death_classes"]["version"])
    for d in ("2026-08-17", "2026-08-18", "2026-08-19"):
        _plant_point(st, "death_occurrences", do_v, d, value=2, numerator=2)
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"old-{d[-2:]}": 1})
    for d in ("2026-08-20", "2026-08-21", "2026-08-22"):
        _plant_point(st, "death_occurrences", do_v - 1, d, value=1, numerator=1)
        _plant_point(st, "death_classes", dc_v, d, value={f"new-{d[-2:]}": 1})
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[2] == DASH, (
        "no day contributes both halves at the current definition — publishing "
        "would mix disjoint definitions"
    )
    err = capsys.readouterr().err
    assert "share no current-definition day" in err


# ── fix-wave 11 (W11: annotations honest to the letter) ──────────────────────────────


def test_split_week_annotation_never_claims_unmixed_for_a_pair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W11-2: a partial-overlap split week (halves bumped on different days)
    publishes with the * and the per-half line — but the note must not claim
    'earlier days ... are not mixed in' while the occurrence sum spans days the
    class set lacks; each number covers only its own metric's current-definition
    days, and the note says exactly that."""
    st = tmp_path / "state"
    reg = _full_reg()
    do_v = int(reg["death_occurrences"]["version"])
    dc_v = int(reg["death_classes"]["version"])
    for d in ("2026-08-19", "2026-08-20", "2026-08-21", "2026-08-22"):
        _plant_point(st, "death_occurrences", do_v, d, value=2, numerator=2)
    for d in ("2026-08-17", "2026-08-18"):
        _plant_point(st, "death_occurrences", do_v - 1, d, value=1, numerator=1)
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"old-{d[-2:]}": 1})
    for d in ("2026-08-19", "2026-08-20"):
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"old-{d[-2:]}": 1})
    for d in ("2026-08-21", "2026-08-22"):
        _plant_point(st, "death_classes", dc_v, d, value={f"new-{d[-2:]}": 1})
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[2] == "8 occ / 2 cls*", (
        "the adjudicated partial-overlap publish: each half over its own "
        "current-definition days, starred and disclosed per half"
    )
    err = capsys.readouterr().err
    assert "not mixed in" not in err
    assert "covers only its metric's current-definition days" in err


def test_ratio_cell_dash_distinguishes_invalid_points_from_no_points(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W11-7: a week whose gate points all carry an invalid denominator dashes
    saying the points were invalid — 'no published days this week' would be
    false (days WERE published)."""
    st = tmp_path / "state"
    reg = _full_reg()
    fa_v = int(reg["first_attempt_gate_pass"]["version"])
    _plant_point(st, "first_attempt_gate_pass", fa_v, "2026-08-18", numerator=1, denominator=0)
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[1] == DASH
    err = capsys.readouterr().err
    assert "none carries a summable numerator/denominator" in err
    assert "Gate first-pass rate = — — no published days this week" not in err


# ── fix-wave 12 (W12: the fail-open is genuinely visible) ────────────────────────────


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the mode bits this test relies on")
def test_unreadable_series_dir_warns_when_probing_older_versions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W12-3: Path.glob swallows PermissionError internally, so W11-4's warn
    never fired for the dominant unreadable-dir cause — the probe must LIST the
    dir inside the guarded region so the fail-open is visible."""
    st = tmp_path / "state"
    sdir = st / "series"
    sdir.mkdir(parents=True)
    (sdir / "m@v1.jsonl").write_text('{"day": "2026-08-18"}\n', encoding="utf-8")
    sdir.chmod(0o000)
    try:
        out = kc._older_version_week_days("m", 2, ["2026-08-18"], st)
    finally:
        sdir.chmod(0o755)
    assert out == set()
    err = capsys.readouterr().err
    assert "series dir unreadable" in err, "the silent fail-open disables two fabrication guards"


# ── fix-wave 13 (W13: the warn means what it says) ───────────────────────────────────


def test_first_publish_emits_no_unreadable_warn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W13-1: a metric's FIRST publish (and every post-bump first publish) reads
    a series file that does not exist yet — that is the normal path, not an
    unreadable file; warning there trains the operator to ignore the real
    fail-open warn W12-3 added."""
    st = tmp_path / "state"
    reg = _full_reg()
    mid = "first_attempt_gate_pass"
    kc.publish_series(
        "2026-08-18",
        {
            mid: kc.MetricResult(
                id=mid, cell="100% (1/1)", detail="probe", value=1.0, numerator=1, denominator=1
            )
        },
        {mid: reg[mid]},
        state=st,
    )
    err = capsys.readouterr().err
    assert "unreadable" not in err, err


# ── fix-wave 15 (W15: the disclosure gating is guarded; split weeks visible on every dash) ──


def test_standalone_halves_line_rides_dash_paths_exactly_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W15-1 (round-15 #1): the W13 gating has both failure directions guarded —
    a split week that DASHES discloses the per-half coverage on exactly one
    standalone line (deleting the block loses the disclosure; dropping the DASH
    condition doubles it on publish paths, covered by the publish test's single
    annotate line)."""
    st = tmp_path / "state"
    reg = _full_reg()
    dc_v = int(reg["death_classes"]["version"])
    for d in ("2026-08-17", "2026-08-18", "2026-08-19"):
        _plant_point(st, "death_classes", dc_v - 1, d, value={f"cls-{d[-2:]}": 1})
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[2] == DASH
    err = capsys.readouterr().err
    assert err.count("split-week halves at the current definition") == 1


def test_single_metric_dash_during_a_split_week_discloses_the_split(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W15-2 (round-15 #2): a single-metric cell that dashes for a NON-bump
    reason during a version-split week still names the split — orphan days
    sitting under the previous definition are the actionable context, and the
    suppressed annotate line was the only carrier."""
    st = tmp_path / "state"
    reg = _full_reg()
    fa_v = int(reg["first_attempt_gate_pass"]["version"])
    for d in ("2026-08-17", "2026-08-18", "2026-08-19"):
        _plant_point(st, "first_attempt_gate_pass", fa_v - 1, d, numerator=1, denominator=2)
    _plant_point(st, "first_attempt_gate_pass", fa_v, "2026-08-21", numerator=1, denominator=0)
    cells = kc.log_cells(dt.date(2026, 8, 23), reg, state=st)
    assert cells[1] == DASH, "one current point with denominator 0 — unmeasurable"
    err = capsys.readouterr().err
    assert "week day(s) under a previous definition" in err, (
        "the dash suppressed the annotate line — the split context must still reach the operator"
    )
