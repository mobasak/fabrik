"""Tests for scripts/kpi_tracker.py."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.kpi_tracker import (
    KPIEvent,
    cmd_ingest,
    cmd_prune,
    cmd_sanitize,
    cmd_summary,
    load_events,
    save_events,
)


@pytest.fixture
def kpi_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temporary .droid directory and patch KPI_DIR."""
    droid_dir = tmp_path / ".droid"
    droid_dir.mkdir()
    monkeypatch.setattr("scripts.kpi_tracker.KPI_DIR", droid_dir)
    monkeypatch.setattr("scripts.kpi_tracker.KPI_FILE", droid_dir / "kpis.jsonl")
    return droid_dir


@pytest.fixture
def sample_event() -> KPIEvent:
    """Create a sample valid KPI event."""
    return KPIEvent(
        event_id=str(uuid.uuid4()),
        event_type="task_end",
        timestamp=datetime.now(tz=UTC).isoformat(),
        task_id=str(uuid.uuid4()),
        model="claude-sonnet-4-5-20250929",
        tokens_input=1000,
        tokens_output=500,
        duration_seconds=30.5,
        status="success",
    )


class TestSchemaValidation:
    """Tests for schema validation and parsing."""

    def test_schema_validation_valid_event(self, kpi_dir: Path, sample_event: KPIEvent) -> None:
        """load_events parses a well-formed JSONL line into KPIEvent."""
        kpi_file = kpi_dir / "kpis.jsonl"
        kpi_file.write_text(json.dumps(sample_event.to_dict()) + "\n")

        events = load_events(kpi_file)

        assert len(events) == 1
        assert events[0].event_id == sample_event.event_id
        assert events[0].event_type == "task_end"
        assert events[0].model == "claude-sonnet-4-5-20250929"

    def test_schema_validation_invalid_event(self, kpi_dir: Path, sample_event: KPIEvent) -> None:
        """Malformed JSON line is skipped; valid lines still returned."""
        kpi_file = kpi_dir / "kpis.jsonl"
        content = "not valid json\n" + json.dumps(sample_event.to_dict()) + "\n"
        kpi_file.write_text(content)

        events = load_events(kpi_file)

        assert len(events) == 1
        assert events[0].event_id == sample_event.event_id


class TestIdempotency:
    """Tests for event deduplication."""

    def test_idempotency_duplicate_event_id(self, kpi_dir: Path) -> None:
        """Second event with same event_id is deduplicated."""
        event_id = str(uuid.uuid4())
        event1 = KPIEvent(
            event_id=event_id,
            event_type="task_end",
            timestamp="2026-02-19T10:00:00Z",
            task_id="task-1",
        )
        event2 = KPIEvent(
            event_id=event_id,
            event_type="task_end",
            timestamp="2026-02-19T11:00:00Z",
            task_id="task-2",
        )

        kpi_file = kpi_dir / "kpis.jsonl"
        kpi_file.write_text(
            json.dumps(event1.to_dict()) + "\n" + json.dumps(event2.to_dict()) + "\n"
        )

        events = load_events(kpi_file)

        assert len(events) == 1
        assert events[0].task_id == "task-1"


class TestFileCorruption:
    """Tests for handling corrupted files."""

    def test_file_corruption_malformed_jsonl(self, kpi_dir: Path) -> None:
        """Mixed valid/invalid lines: valid ones returned, invalid skipped."""
        valid_event = KPIEvent(
            event_id="valid-1",
            event_type="task_start",
            timestamp="2026-02-19T10:00:00Z",
            task_id="task-1",
        )
        valid_event2 = KPIEvent(
            event_id="valid-2",
            event_type="task_end",
            timestamp="2026-02-19T10:05:00Z",
            task_id="task-1",
        )

        kpi_file = kpi_dir / "kpis.jsonl"
        content = (
            json.dumps(valid_event.to_dict())
            + "\n"
            + "corrupted line here\n"
            + "{incomplete json\n"
            + json.dumps(valid_event2.to_dict())
            + "\n"
        )
        kpi_file.write_text(content)

        events = load_events(kpi_file)

        assert len(events) == 2
        assert events[0].event_id == "valid-1"
        assert events[1].event_id == "valid-2"


class TestEmptyFile:
    """Tests for empty file handling."""

    def test_empty_file_handling(self, kpi_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty .droid/kpis.jsonl → summary exits 1, no crash."""
        kpi_file = kpi_dir / "kpis.jsonl"
        kpi_file.write_text("")

        class Args:
            since = None
            until = None
            model = None
            format = "json"

        result = cmd_summary(Args())

        assert result == 1


class TestSummaryCalculation:
    """Tests for summary statistics."""

    def test_summary_calculation(self, kpi_dir: Path, capsys: pytest.CaptureFixture) -> None:
        """Given known events, summary returns correct totals."""
        events = [
            KPIEvent(
                event_id="e1",
                event_type="task_end",
                timestamp="2026-02-19T10:00:00Z",
                task_id="t1",
                model="model-a",
                tokens_input=100,
                tokens_output=50,
                duration_seconds=10.0,
                status="success",
            ),
            KPIEvent(
                event_id="e2",
                event_type="task_end",
                timestamp="2026-02-19T11:00:00Z",
                task_id="t2",
                model="model-a",
                tokens_input=200,
                tokens_output=100,
                duration_seconds=20.0,
                status="success",
            ),
            KPIEvent(
                event_id="e3",
                event_type="task_end",
                timestamp="2026-02-19T12:00:00Z",
                task_id="t3",
                model="model-b",
                tokens_input=300,
                tokens_output=150,
                duration_seconds=30.0,
                status="failure",
            ),
        ]

        kpi_file = kpi_dir / "kpis.jsonl"
        save_events(kpi_file, events)

        class Args:
            since = None
            until = None
            model = None
            format = "json"

        result = cmd_summary(Args())
        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert result == 0
        assert output["summary"]["total_tasks"] == 3
        assert output["summary"]["success_rate"] == round(2 / 3, 4)
        assert output["summary"]["total_tokens"] == 900
        assert output["summary"]["avg_duration_seconds"] == 20.0


class TestPrune:
    """Tests for prune command."""

    def test_prune_retention(self, kpi_dir: Path) -> None:
        """Events older than threshold removed; newer events kept."""
        now = datetime.now(tz=UTC)
        old_event = KPIEvent(
            event_id="old",
            event_type="task_end",
            timestamp=(now - timedelta(days=100)).isoformat(),
            task_id="t1",
        )
        new_event = KPIEvent(
            event_id="new",
            event_type="task_end",
            timestamp=(now - timedelta(days=10)).isoformat(),
            task_id="t2",
        )

        kpi_file = kpi_dir / "kpis.jsonl"
        save_events(kpi_file, [old_event, new_event])

        class Args:
            older_than = "90d"

        result = cmd_prune(Args())

        assert result == 0
        events = load_events(kpi_file)
        assert len(events) == 1
        assert events[0].event_id == "new"


class TestIngest:
    """Tests for ingest command."""

    def test_ingest_from_token_log(self, kpi_dir: Path, tmp_path: Path) -> None:
        """Token log line → deterministic event_id, written to kpis.jsonl."""
        token_log = tmp_path / "token_usage.jsonl"
        token_entry = {
            "timestamp": "2026-02-19T10:00:00Z",
            "session_id": "session-123",
            "model": "claude-sonnet-4-5-20250929",
            "context_key": "test",
            "input_tokens": 500,
            "output_tokens": 200,
            "total_tokens": 700,
        }
        token_log.write_text(json.dumps(token_entry) + "\n")

        class Args:
            source = str(token_log)

        result = cmd_ingest(Args())

        assert result == 0

        kpi_file = kpi_dir / "kpis.jsonl"
        events = load_events(kpi_file)

        assert len(events) == 1
        assert events[0].event_type == "task_end"
        assert events[0].model == "claude-sonnet-4-5-20250929"
        assert events[0].tokens_input == 500
        assert events[0].tokens_output == 200

        expected_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "session-123" + "2026-02-19T10:00:00Z"))
        assert events[0].event_id == expected_id


class TestSanitize:
    """Tests for sanitize command."""

    def test_sanitize_error_message(self, kpi_dir: Path) -> None:
        """Path strings stripped from error_message field."""
        event = KPIEvent(
            event_id="e1",
            event_type="error",
            timestamp="2026-02-19T10:00:00Z",
            task_id="t1",
            error_message='Error at /home/user/secret/file.py: File "/usr/lib/python/traceback.py" failed',
        )

        kpi_file = kpi_dir / "kpis.jsonl"
        save_events(kpi_file, [event])

        class Args:
            field = "error_message"

        result = cmd_sanitize(Args())

        assert result == 0
        events = load_events(kpi_file)
        assert len(events) == 1
        assert "/home/user" not in events[0].error_message
        assert "/usr/lib" not in events[0].error_message
        assert "[PATH]" in events[0].error_message or "[REDACTED]" in events[0].error_message
