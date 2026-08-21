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


def test_daily_publishes_outcome_tier_series(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M7: the store-derived outcome tier (premature_stop / stop_block_causes /
    review_rounds) publishes its series days from the SAME daily pass."""
    monkeypatch.setenv("KAIZEN_OUTCOMES_WINDOW_DAYS", "36500")
    rc, _, st, _ = _green_daily(tmp_path, dt.date.today())
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


def test_death_cell_dashes_when_coroner_never_ran() -> None:
    """M9: '0 occ / 0 cls' while the coroner has never run is a fabricated zero —
    dash with the reason; a genuine coroner-backed zero still prints."""
    base = {
        "sid": "s",
        "facts_version": kc.FACTS_VERSION,
        "day": "2026-08-18",
        "events": {"stop_pass": 1},
        "death_classes": [],
        "unclassified_reasons": {},
        "stop_causes": {},
        "gate": {"runs": 0, "first_status": None, "pass": 0, "fail": 0, "failed_checks": {}},
        "runs": {"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 0},
        "lines_total": 1,
        "lines_unclassified": 0,
    }
    rows = [base]
    metrics = kc.compute_metrics(rows, holes=None, holes_reason="coroner unavailable")
    cells = kc.log_cells(dt.date(2026, 8, 18), metrics, rows, all_rows=rows)
    assert cells[2] == DASH, "no coroner evidence anywhere -> the cell dashes"
    closed = json.loads(json.dumps(base))
    closed["sid"] = "closed"
    closed["events"] = {"session_end": 1}
    rows2 = [base, closed]
    cells2 = kc.log_cells(dt.date(2026, 8, 18), metrics, rows2, all_rows=rows2)
    assert cells2[2] == "0 occ / 0 cls", "a coroner-backed zero is a genuine zero"


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


def test_log_cells_rounds_dash_when_round_family_unattributable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """W2-F2: a mean over n=1 attributed round-carrying sessions while the round
    mass sits in the unknown stream is fabricated precision — the cell dashes."""
    day = dt.date(2026, 8, 18)
    r1 = _w2_row(
        "s1",
        "2026-08-18",
        events={"round": 1},
        runs={"opened": 1, "done": 1, "done_evidenced": 1, "blocked": 0, "rounds_max": 3},
    )
    unk = _w2_row(
        "unknown",
        "2026-08-18",
        project=None,
        events_unattributed={"round": 47},
        concurrent_reason="unattributable-sid",
    )
    metrics = kc.compute_metrics([r1, unk], holes=0)
    cells = kc.log_cells(day, metrics, [r1, unk], all_rows=[r1, unk])
    assert cells[4] == DASH, "the rounds cell must dash under the attribution floor"
    err = capsys.readouterr().err
    assert "Review rounds" in err and "unattributable" in err


def test_log_cells_rounds_guard_uses_the_store_universe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """W2-F2: the unknown accumulator's row may sit outside the week (its derivation
    day is whenever it last grew) — the guard reads the UNIVERSE, like M9's
    coroner-evidence check, so a week slice cannot hide the unknown mass."""
    day = dt.date(2026, 8, 18)
    r1 = _w2_row(
        "s1",
        "2026-08-18",
        events={"round": 1},
        runs={"opened": 0, "done": 0, "done_evidenced": 0, "blocked": 0, "rounds_max": 2},
    )
    unk_earlier_week = _w2_row(
        "unknown",
        "2026-08-07",
        project=None,
        events_unattributed={"round": 47},
        concurrent_reason="unattributable-sid",
    )
    metrics = kc.compute_metrics([r1], holes=0)
    cells = kc.log_cells(day, metrics, [r1], all_rows=[r1, unk_earlier_week])
    assert cells[4] == DASH


def test_log_cells_death_cell_accepts_v1_scalar_death_class() -> None:
    """W2-F6: a FACTS_VERSION-1 row carries a SCALAR death_class — the class count
    must see it ('2 occ / 0 cls' hid a classified death)."""
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
    metrics = kc.compute_metrics([legacy], holes=0)
    cells = kc.log_cells(dt.date(2026, 8, 18), metrics, [legacy], all_rows=[legacy])
    assert cells[2] == "2 occ / 1 cls"


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


def test_log_cells_rounds_dash_even_when_lifetime_share_passes_floor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """S3 (weekly consumer): the unknown accumulator is TIMELESS, so a windowed
    unattributed count is UNKNOWABLE — any unknown round mass dashes the cell, even
    when the lifetime share passes the old 20% floor (the fails-open case)."""
    day = dt.date(2026, 8, 18)
    r1 = _w2_row(
        "s1",
        "2026-08-18",
        events={"round": 100},
        runs={"opened": 1, "done": 1, "done_evidenced": 1, "blocked": 0, "rounds_max": 3},
    )
    unk = _w2_row(
        "unknown",
        "2026-08-18",
        project=None,
        events_unattributed={"round": 10},
        concurrent_reason="unattributable-sid",
    )
    metrics = kc.compute_metrics([r1, unk], holes=0)
    cells = kc.log_cells(day, metrics, [r1, unk], all_rows=[r1, unk])
    assert cells[4] == DASH, "lifetime share 91% must not buy a windowed publish"
    err = capsys.readouterr().err
    assert "unmeasurable in this window" in err


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
