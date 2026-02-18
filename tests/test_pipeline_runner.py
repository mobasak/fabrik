"""Tests for GAP-09 Pipeline Runner."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.pipeline_runner import (
    ExitCode,
    PipelineConfig,
    PipelineRunner,
    RiskLevel,
    create_parser,
    main,
)


class TestRiskAssessment:
    """Tests for risk assessment logic."""

    def test_assess_risk_low_typo(self) -> None:
        """LOW risk for typo fixes."""
        runner = PipelineRunner()
        assert runner.assess_risk("Fix typo in README") == RiskLevel.LOW

    def test_assess_risk_low_docs(self) -> None:
        """LOW risk for documentation changes."""
        runner = PipelineRunner()
        assert runner.assess_risk("Update docs for users") == RiskLevel.LOW

    def test_assess_risk_low_comment(self) -> None:
        """LOW risk for comment changes."""
        runner = PipelineRunner()
        assert runner.assess_risk("Add comment to function") == RiskLevel.LOW

    def test_assess_risk_medium_feature(self) -> None:
        """MEDIUM risk for feature work."""
        runner = PipelineRunner()
        assert runner.assess_risk("Add new feature for users") == RiskLevel.MEDIUM

    def test_assess_risk_medium_endpoint(self) -> None:
        """MEDIUM risk for endpoint work."""
        runner = PipelineRunner()
        assert runner.assess_risk("Create endpoint for data") == RiskLevel.MEDIUM

    def test_assess_risk_medium_component(self) -> None:
        """MEDIUM risk for component work."""
        runner = PipelineRunner()
        assert runner.assess_risk("Build component for UI") == RiskLevel.MEDIUM

    def test_assess_risk_high_auth(self) -> None:
        """HIGH risk for authentication changes."""
        runner = PipelineRunner()
        assert runner.assess_risk("Add JWT authentication") == RiskLevel.HIGH

    def test_assess_risk_high_security(self) -> None:
        """HIGH risk for security changes."""
        runner = PipelineRunner()
        assert runner.assess_risk("Fix security vulnerability") == RiskLevel.HIGH

    def test_assess_risk_high_database(self) -> None:
        """HIGH risk for database changes."""
        runner = PipelineRunner()
        assert runner.assess_risk("Add database migration") == RiskLevel.HIGH

    def test_assess_risk_high_api(self) -> None:
        """HIGH risk for API changes."""
        runner = PipelineRunner()
        assert runner.assess_risk("Modify API contract") == RiskLevel.HIGH

    def test_assess_risk_unknown_defaults_high(self) -> None:
        """Unknown tasks default to HIGH (fail-safe)."""
        runner = PipelineRunner()
        assert runner.assess_risk("Do something unclear") == RiskLevel.HIGH


class TestRiskRouting:
    """Tests for risk-based stage routing."""

    def test_route_by_risk_low(self) -> None:
        """LOW risk starts at stage 3 (Execution)."""
        runner = PipelineRunner()
        assert runner.route_by_risk(RiskLevel.LOW) == 3

    def test_route_by_risk_medium(self) -> None:
        """MEDIUM risk starts at stage 2 (Planning)."""
        runner = PipelineRunner()
        assert runner.route_by_risk(RiskLevel.MEDIUM) == 2

    def test_route_by_risk_high(self) -> None:
        """HIGH risk starts at stage 1 (Discovery)."""
        runner = PipelineRunner()
        assert runner.route_by_risk(RiskLevel.HIGH) == 1


class TestDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_returns_success_with_flag(self) -> None:
        """Dry run should return status 'success' with dry_run=True."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Test task", dry_run=True)
        assert result.status == "success"
        assert result.dry_run is True

    def test_dry_run_has_run_id(self) -> None:
        """Dry run should generate a run_id."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Test task", dry_run=True)
        assert result.run_id is not None
        assert len(result.run_id) > 0

    def test_dry_run_captures_task(self) -> None:
        """Dry run should capture the task description."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Fix typo in README", dry_run=True)
        assert result.task == "Fix typo in README"

    def test_dry_run_assesses_risk(self) -> None:
        """Dry run should assess and record risk level (uppercase)."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Fix typo", dry_run=True)
        assert result.risk_level == "LOW"


class TestMaxIterations:
    """Tests for verification iteration cap."""

    def test_max_verify_iterations_constant(self) -> None:
        """MAX_VERIFY_ITERATIONS should be 2."""
        assert PipelineRunner.MAX_VERIFY_ITERATIONS == 2

    def test_config_max_verify_iterations(self) -> None:
        """Config should have max_verify_iterations=2."""
        config = PipelineConfig()
        assert config.max_verify_iterations == 2


class TestPipelineConfig:
    """Tests for pipeline configuration."""

    def test_default_stages(self) -> None:
        """Default config should have all 5 stages."""
        config = PipelineConfig()
        assert config.stages == ["discovery", "planning", "execution", "verification", "ship"]

    def test_custom_cwd(self) -> None:
        """Config should accept custom working directory."""
        config = PipelineConfig(cwd="/tmp/test")
        assert config.cwd == "/tmp/test"


class TestCLIParsing:
    """Tests for CLI argument parsing."""

    def test_parser_help_exits_zero(self) -> None:
        """--help should parse without error."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_parser_run_with_task(self) -> None:
        """run subcommand should accept task argument."""
        parser = create_parser()
        args = parser.parse_args(["run", "Test task"])
        assert args.command == "run"
        assert args.task == "Test task"

    def test_parser_run_dry_run_flag(self) -> None:
        """--dry-run flag should be parsed."""
        parser = create_parser()
        args = parser.parse_args(["run", "Test", "--dry-run"])
        assert args.dry_run is True

    def test_parser_run_risk_override(self) -> None:
        """--risk flag should accept low/medium/high."""
        parser = create_parser()
        args = parser.parse_args(["run", "Test", "--risk", "high"])
        assert args.risk == "high"

    def test_parser_run_stage_override(self) -> None:
        """--stage flag should accept stage names."""
        parser = create_parser()
        args = parser.parse_args(["run", "Test", "--stage", "execution"])
        assert args.stage == "execution"

    def test_parser_run_json_flag(self) -> None:
        """--json flag should be parsed."""
        parser = create_parser()
        args = parser.parse_args(["run", "Test", "--json"])
        assert args.json is True

    def test_parser_stage_subcommand(self) -> None:
        """stage subcommand should accept stage_name and task."""
        parser = create_parser()
        args = parser.parse_args(["stage", "discovery", "Analyze code"])
        assert args.command == "stage"
        assert args.stage_name == "discovery"
        assert args.task == "Analyze code"


class TestRiskOverride:
    """Tests for --risk override functionality."""

    def test_risk_override_low(self) -> None:
        """--risk low should override automatic assessment."""
        runner = PipelineRunner()
        result = runner.run_pipeline(
            "Add authentication",  # Would be HIGH
            dry_run=True,
            risk_override=RiskLevel.LOW,
        )
        assert result.risk_level == "LOW"

    def test_risk_override_high(self) -> None:
        """--risk high should override automatic assessment."""
        runner = PipelineRunner()
        result = runner.run_pipeline(
            "Fix typo",  # Would be LOW
            dry_run=True,
            risk_override=RiskLevel.HIGH,
        )
        assert result.risk_level == "HIGH"


class TestStageOverride:
    """Tests for --stage override functionality."""

    def test_stage_override_skips_stages(self) -> None:
        """--stage execution should skip discovery and planning."""
        runner = PipelineRunner()
        result = runner.run_pipeline(
            "Add authentication",  # Would start at stage 1
            dry_run=True,
            start_stage=3,  # Start at execution
        )
        assert result.metrics["stages_skipped"] == 2


class TestJsonOutput:
    """Tests for --json output functionality."""

    def test_json_output_is_valid(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--json should output valid JSON."""
        with patch.object(sys, "argv", ["prog", "run", "Test", "--dry-run", "--json"]):
            exit_code = main()
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "run_id" in data
        assert "status" in data
        assert "timestamps" in data
        assert "metrics" in data


class TestReportContract:
    """Tests for report.json contract and latest pointer."""

    @pytest.fixture
    def temp_cwd(self, tmp_path: Path) -> Path:
        """Create a temporary working directory."""
        return tmp_path

    def test_save_report_creates_json(self, temp_cwd: Path) -> None:
        """save_report should create report.json with required keys."""
        config = PipelineConfig(cwd=str(temp_cwd))
        runner = PipelineRunner(config)
        result = runner.run_pipeline("Test task", dry_run=False)
        report_path = runner.save_report(result)

        assert report_path.exists()
        with open(report_path) as f:
            data = json.load(f)

        assert "run_id" in data
        assert "task" in data
        assert "risk_level" in data
        assert "status" in data
        assert "stages" in data
        assert "timestamps" in data
        assert "metrics" in data
        assert "started_at" in data["timestamps"]
        assert "ended_at" in data["timestamps"]
        assert "duration_seconds" in data["timestamps"]

    def test_save_report_creates_latest_symlink_on_linux(self, temp_cwd: Path) -> None:
        """save_report should create latest symlink on Linux/WSL."""
        config = PipelineConfig(cwd=str(temp_cwd))
        runner = PipelineRunner(config)
        result = runner.run_pipeline("Test task", dry_run=False)
        runner.save_report(result)

        latest_link = temp_cwd / ".factory" / "reports" / "latest"
        if latest_link.is_symlink():
            # Linux/WSL: symlink should point to run_id (use readlink for robustness)
            import os

            assert os.readlink(latest_link) == result.run_id
        else:
            # Windows fallback: latest.txt should contain run_id
            latest_txt = temp_cwd / ".factory" / "reports" / "latest.txt"
            assert latest_txt.exists()
            assert latest_txt.read_text() == result.run_id

    def test_save_report_updates_latest_on_second_run(self, temp_cwd: Path) -> None:
        """Second run should update latest pointer."""
        config = PipelineConfig(cwd=str(temp_cwd))

        # First run
        runner1 = PipelineRunner(config)
        result1 = runner1.run_pipeline("First task", dry_run=False)
        runner1.save_report(result1)

        # Second run
        runner2 = PipelineRunner(config)
        result2 = runner2.run_pipeline("Second task", dry_run=False)
        runner2.save_report(result2)

        latest_link = temp_cwd / ".factory" / "reports" / "latest"
        if latest_link.is_symlink():
            import os

            assert os.readlink(latest_link) == result2.run_id
        else:
            latest_txt = temp_cwd / ".factory" / "reports" / "latest.txt"
            assert latest_txt.read_text() == result2.run_id

    def test_metrics_stages_skipped_consistent(self, temp_cwd: Path) -> None:
        """stages_skipped should be consistent with risk routing."""
        config = PipelineConfig(cwd=str(temp_cwd))
        runner = PipelineRunner(config)

        # LOW risk skips 2 stages (discovery, planning)
        result = runner.run_pipeline("Fix typo", dry_run=False)
        assert result.metrics["stages_skipped"] == 2

        # HIGH risk skips 0 stages
        result_high = runner.run_pipeline("Add auth", dry_run=False)
        assert result_high.metrics["stages_skipped"] == 0

    def test_timestamps_are_iso_format(self, temp_cwd: Path) -> None:
        """Timestamps should be ISO 8601 format."""
        config = PipelineConfig(cwd=str(temp_cwd))
        runner = PipelineRunner(config)
        result = runner.run_pipeline("Test", dry_run=False)

        from datetime import datetime

        # Should parse without error
        datetime.fromisoformat(result.timestamps["started_at"])
        datetime.fromisoformat(result.timestamps["ended_at"])

    def test_duration_seconds_is_numeric(self, temp_cwd: Path) -> None:
        """duration_seconds should be numeric (placeholder 0.0 is acceptable)."""
        config = PipelineConfig(cwd=str(temp_cwd))
        runner = PipelineRunner(config)
        result = runner.run_pipeline("Test", dry_run=False)

        assert isinstance(result.timestamps["duration_seconds"], (int, float))


class TestExitCodes:
    """Tests for GAP-09 failure matrix exit codes."""

    def test_exit_code_enum_values(self) -> None:
        """ExitCode enum should have correct values per GAP-09."""
        assert ExitCode.SUCCESS.value == 0
        assert ExitCode.STAGE_EXECUTION_FAILED.value == 1
        assert ExitCode.VERIFICATION_REJECTED_TWICE.value == 2
        assert ExitCode.MODEL_NOT_AVAILABLE.value == 3
        assert ExitCode.PREFLIGHT_GATE_FAILED.value == 4
        assert ExitCode.RISK_ASSESSMENT_FAILED.value == 5

    def test_success_exit_code(self) -> None:
        """Successful run should have exit_code=0."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Test task", dry_run=True)
        assert result.exit_code == 0

    def test_dry_run_exit_code(self) -> None:
        """Dry run should have exit_code=0."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Test task", dry_run=True)
        assert result.exit_code == ExitCode.SUCCESS.value


class TestReportContractCompliance:
    """Tests for GAP-09 report contract compliance."""

    def test_report_has_total_tokens_key(self) -> None:
        """Report must use total_tokens (not total_tokens_used)."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Test", dry_run=True)
        assert "total_tokens" in result.metrics
        assert "total_tokens_used" not in result.metrics

    def test_report_risk_level_uppercase(self) -> None:
        """Report risk_level must be uppercase."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Add auth", dry_run=True)
        assert result.risk_level == "HIGH"
        assert result.risk_level in ("LOW", "MEDIUM", "HIGH")

    def test_report_has_dry_run_flag(self) -> None:
        """Report must have dry_run boolean field."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Test", dry_run=True)
        assert hasattr(result, "dry_run")
        assert result.dry_run is True

    def test_report_non_dry_run_has_false_flag(self, tmp_path: Path) -> None:
        """Non-dry-run should have dry_run=False."""
        config = PipelineConfig(cwd=str(tmp_path))
        runner = PipelineRunner(config)
        result = runner.run_pipeline("Test", dry_run=False)
        assert result.dry_run is False

    def test_report_status_in_allowed_values(self) -> None:
        """Report status must be in {success, failed, escalated}."""
        runner = PipelineRunner()
        result = runner.run_pipeline("Test", dry_run=True)
        assert result.status in ("success", "failed", "escalated")


class TestStage1Discovery:
    """Tests for Stage 1 Discovery implementation."""

    def test_discovery_returns_stage_result(self) -> None:
        """run_stage_1_discovery should return StageResult."""
        from scripts.pipeline_runner import StageResult

        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            # Mock the TaskResult and MultiModelResult
            mock_task_result = type(
                "TaskResult",
                (),
                {
                    "success": True,
                    "session_id": "test-session-123",
                    "result": "Analysis output here",
                },
            )()
            mock_multi_result = type(
                "MultiModelResult",
                (),
                {
                    "primary_result": mock_task_result,
                    "merged_result": "Merged analysis output",
                },
            )()
            mock_discovery.return_value = mock_multi_result

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test task")

            assert isinstance(result, StageResult)
            assert result.stage == "discovery"

    def test_discovery_captures_session_id(self) -> None:
        """Discovery should capture and store session_id."""
        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            mock_task_result = type(
                "TaskResult",
                (),
                {
                    "success": True,
                    "session_id": "captured-session-id",
                    "result": "Output",
                },
            )()
            mock_multi_result = type(
                "MultiModelResult",
                (),
                {
                    "primary_result": mock_task_result,
                    "merged_result": "Merged output",
                },
            )()
            mock_discovery.return_value = mock_multi_result

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test task")

            assert result.session_id == "captured-session-id"
            assert runner.config.session_ids["discovery"] == "captured-session-id"

    def test_discovery_pass_on_success(self) -> None:
        """Discovery should return status='pass' on success."""
        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            mock_task_result = type(
                "TaskResult",
                (),
                {
                    "success": True,
                    "session_id": "sess-1",
                    "result": "Output",
                },
            )()
            mock_multi_result = type(
                "MultiModelResult",
                (),
                {
                    "primary_result": mock_task_result,
                    "merged_result": "Merged",
                },
            )()
            mock_discovery.return_value = mock_multi_result

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test")

            assert result.status == "pass"

    def test_discovery_fail_on_error(self) -> None:
        """Discovery should return status='fail' on error."""
        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            mock_discovery.side_effect = RuntimeError("Model unavailable")

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test")

            assert result.status == "fail"
            assert "Error:" in result.output

    def test_discovery_has_timestamps(self) -> None:
        """Discovery result should have ISO timestamps."""
        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            mock_task_result = type(
                "TaskResult",
                (),
                {
                    "success": True,
                    "session_id": "sess",
                    "result": "Output",
                },
            )()
            mock_multi_result = type(
                "MultiModelResult",
                (),
                {
                    "primary_result": mock_task_result,
                    "merged_result": "Merged",
                },
            )()
            mock_discovery.return_value = mock_multi_result

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test")

            # Verify timestamps are valid ISO format
            from datetime import datetime

            datetime.fromisoformat(result.started_at)
            datetime.fromisoformat(result.ended_at)

    def test_discovery_preserves_full_output(self) -> None:
        """Discovery should preserve full output (truncation happens in report mapping)."""
        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            long_output = "x" * 1000
            mock_task_result = type(
                "TaskResult",
                (),
                {
                    "success": True,
                    "session_id": "sess",
                    "result": long_output,
                },
            )()
            mock_multi_result = type(
                "MultiModelResult",
                (),
                {
                    "primary_result": mock_task_result,
                    "merged_result": long_output,
                },
            )()
            mock_discovery.return_value = mock_multi_result

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test")

            # Full output preserved in StageResult
            assert len(result.output) == 1000

    def test_discovery_tokens_used_zero(self) -> None:
        """Discovery should set tokens_used=0 (no estimation)."""
        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            mock_task_result = type(
                "TaskResult",
                (),
                {
                    "success": True,
                    "session_id": "sess",
                    "result": "Output",
                },
            )()
            mock_multi_result = type(
                "MultiModelResult",
                (),
                {
                    "primary_result": mock_task_result,
                    "merged_result": "Output",
                },
            )()
            mock_discovery.return_value = mock_multi_result

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test")

            assert result.tokens_used == 0

    def test_discovery_model_is_unknown(self) -> None:
        """Discovery should set model='unknown' (not 'dual-model')."""
        with patch("scripts.droid_core.run_discovery_dual_model") as mock_discovery:
            mock_task_result = type(
                "TaskResult",
                (),
                {
                    "success": True,
                    "session_id": "sess",
                    "result": "Output",
                },
            )()
            mock_multi_result = type(
                "MultiModelResult",
                (),
                {
                    "primary_result": mock_task_result,
                    "merged_result": "Output",
                },
            )()
            mock_discovery.return_value = mock_multi_result

            runner = PipelineRunner()
            result = runner.run_stage_1_discovery("Test")

            assert result.model == "unknown"


class TestStageResultToReportStage:
    """Tests for stage_result_to_report_stage helper."""

    def test_truncates_output_to_500(self) -> None:
        """Helper should truncate output to 500 chars for output_summary."""
        from scripts.pipeline_runner import StageResult, stage_result_to_report_stage

        sr = StageResult(
            stage="discovery",
            status="pass",
            started_at="2026-01-01T00:00:00+00:00",
            ended_at="2026-01-01T00:00:01+00:00",
            session_id="sess-1",
            model="unknown",
            output="x" * 1000,
            tokens_used=0,
        )
        report = stage_result_to_report_stage(sr)

        assert len(report["output_summary"]) == 500
        assert report["stage"] == "discovery"
        assert report["status"] == "pass"

    def test_preserves_short_output(self) -> None:
        """Helper should preserve short output as-is."""
        from scripts.pipeline_runner import StageResult, stage_result_to_report_stage

        sr = StageResult(
            stage="planning",
            status="pass",
            started_at="2026-01-01T00:00:00+00:00",
            ended_at="2026-01-01T00:00:01+00:00",
            session_id="sess-2",
            model="unknown",
            output="short output",
            tokens_used=0,
        )
        report = stage_result_to_report_stage(sr)

        assert report["output_summary"] == "short output"

    def test_handles_empty_output(self) -> None:
        """Helper should handle empty output gracefully."""
        from scripts.pipeline_runner import StageResult, stage_result_to_report_stage

        sr = StageResult(
            stage="execution",
            status="fail",
            started_at="2026-01-01T00:00:00+00:00",
            ended_at="2026-01-01T00:00:01+00:00",
            session_id="sess-3",
            model="none",
            output="",
            tokens_used=0,
        )
        report = stage_result_to_report_stage(sr)

        assert report["output_summary"] == ""
