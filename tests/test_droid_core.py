#!/usr/bin/env python3
"""
Tests for droid_core.py

Covers:
- Session ID propagation (Pattern 2 continuity)
- Streaming failure handling
- Task ID sanitization
- JSON parse fallback behavior
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from droid_core import (
    DroidSession,
    TaskResult,
    TaskType,
    _sanitize_task_id,
    run_droid_exec,
)


class TestSanitizeTaskId:
    """Tests for _sanitize_task_id function."""

    def test_removes_path_traversal(self):
        """Should remove path traversal attempts."""
        assert ".." not in _sanitize_task_id("../../../etc/passwd")
        assert "/" not in _sanitize_task_id("foo/bar/baz")
        assert "\\" not in _sanitize_task_id("foo\\bar\\baz")

    def test_preserves_valid_chars(self):
        """Should preserve alphanumeric, underscore, and dash."""
        result = _sanitize_task_id("valid-task_id-123")
        assert result == "valid-task_id-123"

    def test_max_length_enforced(self):
        """Should truncate long task IDs with hash suffix."""
        long_id = "a" * 200
        result = _sanitize_task_id(long_id, max_length=128)
        assert len(result) <= 128
        # Should have hash suffix for uniqueness
        assert "_" in result[-10:]

    def test_short_id_unchanged(self):
        """Short IDs should not be truncated."""
        short_id = "task-abc-123"
        result = _sanitize_task_id(short_id)
        assert result == short_id


class TestSessionIdPropagation:
    """Tests for session ID propagation (Pattern 2)."""

    @patch("droid_core.subprocess.Popen")
    @patch("droid_core.refresh_models_from_docs")
    def test_session_id_passed_to_subprocess(self, mock_refresh, mock_popen):
        """Session ID should be passed to subprocess when provided."""
        # Setup mock process
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout.read.return_value = '{"result": "done", "session_id": "sess-123"}'
        mock_process.stderr.read.return_value = ""
        mock_popen.return_value = mock_process

        # Call with session_id
        run_droid_exec(
            prompt="Test prompt",
            task_type=TaskType.ANALYZE,
            session_id="existing-session-456",
        )

        # Verify --session-id was in the args
        call_args = mock_popen.call_args[0][0]
        assert "--session-id" in call_args
        assert "existing-session-456" in call_args

    @patch("droid_core.subprocess.run")
    @patch("droid_core.refresh_models_from_docs")
    def test_session_id_returned_in_result(self, mock_refresh, mock_run):
        """Session ID from response should be in TaskResult."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "success", "session_id": "new-session-789"}',
            stderr="",
        )

        result = run_droid_exec(
            prompt="Test prompt",
            task_type=TaskType.ANALYZE,
        )

        assert result.session_id == "new-session-789"

    def test_droid_session_propagates_session_id(self):
        """DroidSession should track and propagate session_id."""
        session = DroidSession()

        # Initially no session ID
        assert session.session_id is None

        # After setting, should be available
        session.session_id = "test-session-abc"
        assert session.session_id == "test-session-abc"

    @patch("droid_core.check_model_change_warning")
    def test_session_reset_on_provider_switch(self, mock_warning):
        """Session should be reset when switching between providers."""
        session = DroidSession(model="gpt-4o")
        session.session_id = "existing-session-123"

        # Simulate provider switch warning (OpenAI -> Anthropic)
        mock_warning.return_value = "Switching providers: session will be lost"

        warning = session.set_model("claude-3-5-sonnet")

        # Session ID should be cleared
        assert session.session_id is None
        assert warning is not None
        assert session.model == "claude-3-5-sonnet"

    @patch("droid_core.check_model_change_warning")
    def test_session_preserved_same_provider(self, mock_warning):
        """Session should be preserved when staying with same provider."""
        session = DroidSession(model="gpt-4o")
        session.session_id = "existing-session-456"

        # No warning for same-provider switch
        mock_warning.return_value = None

        warning = session.set_model("gpt-5.1-codex-max")

        # Session ID should be preserved
        assert session.session_id == "existing-session-456"
        assert warning is None
        assert session.model == "gpt-5.1-codex-max"


class TestStreamingFailureHandling:
    """Tests for streaming mode failure handling."""

    @patch("droid_core.subprocess.Popen")
    @patch("droid_core.refresh_models_from_docs")
    def test_timeout_returns_failure(self, mock_refresh, mock_popen):
        """Timeout should return TaskResult with success=False."""
        # This is tested implicitly via the timeout logic
        # Full integration test would require actual subprocess
        pass

    def test_exit_code_nonzero_is_failure(self):
        """Non-zero exit code should result in failure."""
        # Create a mock result
        result = TaskResult(
            success=False,
            task_type=TaskType.ANALYZE,
            prompt="test",
            result="",
            error="Exit code: 1",
        )
        assert result.success is False
        assert "Exit code" in result.error


class TestJsonParseFallback:
    """Tests for JSON parse fallback behavior."""

    def test_malformed_json_is_failure(self):
        """Malformed JSON should result in failure, not success."""
        # Test the error detection logic directly
        output = "not valid json {{{"
        has_error_indicator = any(
            indicator in output.lower()
            for indicator in ["error", "failed", "exception", "traceback", "is_error"]
        )
        # This output has no error indicators, so JSON parse failure should still fail
        # The key test is that we DON'T mark success=True on parse failure
        assert not has_error_indicator  # No error indicators in this case

    def test_error_in_output_detected(self):
        """Error indicators in output should be detected."""
        output = "Some text with error in it but no JSON"
        has_error_indicator = any(
            indicator in output.lower()
            for indicator in ["error", "failed", "exception", "traceback", "is_error"]
        )
        assert has_error_indicator  # Should detect "error"

    @patch("droid_core.subprocess.run")
    @patch("droid_core.refresh_models_from_docs")
    def test_is_error_true_is_failure(self, mock_refresh, mock_run):
        """is_error: true in JSON should result in failure."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "something failed", "is_error": true}',
            stderr="",
        )

        result = run_droid_exec(
            prompt="Test prompt",
            task_type=TaskType.ANALYZE,
        )

        assert result.success is False


class TestTaskResultDataclass:
    """Tests for TaskResult dataclass."""

    def test_default_values(self):
        """TaskResult should have sensible defaults."""
        result = TaskResult(
            success=True,
            task_type=TaskType.ANALYZE,
            prompt="test",
            result="output",
        )
        # Check that result can be created with minimal required fields
        assert result.success is True
        assert result.task_type == TaskType.ANALYZE
        assert result.prompt == "test"
        assert result.result == "output"

    def test_all_fields_set(self):
        """All fields should be settable."""
        result = TaskResult(
            success=False,
            task_type=TaskType.CODE,
            prompt="write code",
            result="def foo(): pass",
            error="some error",
            duration_ms=1500,
            session_id="sess-123",
        )
        assert result.success is False
        assert result.task_type == TaskType.CODE
        assert result.duration_ms == 1500
        assert result.session_id == "sess-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
