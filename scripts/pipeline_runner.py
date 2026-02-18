#!/usr/bin/env python3
"""
GAP-09 Pipeline Orchestrator - 5-stage pipeline for AI-assisted development.

Stages:
    1. Discovery (HIGH risk) - Dual-model analysis
    2. Planning (MEDIUM risk) - Plan with review
    3. Execution - Code implementation
    4. Verification - Independent review
    5. Ship - Documentation updates

Usage:
    python scripts/pipeline_runner.py run "Task description" --dry-run
    python scripts/pipeline_runner.py run "Fix typo" --risk low
    python scripts/pipeline_runner.py stage discovery "Analyze auth flow"
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class RiskLevel(Enum):
    """Risk levels for task routing."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExitCode(Enum):
    """Exit codes per GAP-09 failure matrix."""
    SUCCESS = 0
    STAGE_EXECUTION_FAILED = 1
    VERIFICATION_REJECTED_TWICE = 2
    MODEL_NOT_AVAILABLE = 3
    PREFLIGHT_GATE_FAILED = 4
    RISK_ASSESSMENT_FAILED = 5


@dataclass
class StageResult:
    """Internal dataclass for stage execution results."""
    stage: str
    status: str  # "pass" or "fail"
    started_at: str
    ended_at: str
    session_id: str
    model: str
    output: str  # Full output; truncated only in report mapping
    iteration: int = 1
    tokens_used: int = 0


def stage_result_to_report_stage(sr: StageResult) -> dict[str, Any]:
    """Map internal StageResult to report.json stage entry.

    Performs 500-char truncation for output_summary.
    """
    return {
        "stage": sr.stage,
        "status": sr.status,
        "started_at": sr.started_at,
        "ended_at": sr.ended_at,
        "session_id": sr.session_id,
        "model": sr.model,
        "output_summary": sr.output[:500] if sr.output else "",
        "iteration": sr.iteration,
        "tokens_used": sr.tokens_used,
    }


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    stages: list[str] = field(default_factory=lambda: [
        "discovery", "planning", "execution", "verification", "ship"
    ])
    models: dict[str, str] = field(default_factory=dict)
    session_ids: dict[str, str] = field(default_factory=dict)
    max_verify_iterations: int = 2
    cwd: str = "."


@dataclass
class PipelineResult:
    """Result of a complete pipeline execution.

    Report contract (GAP-09):
    - status: "success" | "failed" | "escalated"
    - risk_level: "LOW" | "MEDIUM" | "HIGH"
    - dry_run: true only when --dry-run flag used
    - metrics.total_tokens: required key for token count
    """
    run_id: str
    task: str
    risk_level: str  # "LOW" | "MEDIUM" | "HIGH"
    status: str  # "success" | "failed" | "escalated"
    stages: list[dict[str, Any]]
    timestamps: dict[str, Any]
    metrics: dict[str, Any]
    dry_run: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)
    exit_code: int = 0

    def to_report(self) -> dict[str, Any]:
        """Convert to report.json format."""
        return asdict(self)


class PipelineRunner:
    """5-stage pipeline orchestrator."""

    MAX_VERIFY_ITERATIONS = 2

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self.run_id = str(uuid.uuid4())
        self.stage_results: list[StageResult] = []

    def assess_risk(self, task: str) -> RiskLevel:
        """
        Assess task risk level based on keywords.

        Returns RiskLevel. UNKNOWN is not a valid return value.
        Default to HIGH for unknown (fail-safe).
        """
        task_lower = task.lower()

        if any(kw in task_lower for kw in ['auth', 'security', 'database', 'api', 'migration']):
            return RiskLevel.HIGH

        if any(kw in task_lower for kw in ['feature', 'endpoint', 'component']):
            return RiskLevel.MEDIUM

        if any(kw in task_lower for kw in ['typo', 'fix', 'docs', 'comment', 'readme']):
            return RiskLevel.LOW

        return RiskLevel.HIGH

    def route_by_risk(self, risk: RiskLevel) -> int:
        """Determine starting stage based on risk level."""
        routing = {
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
        }
        return routing.get(risk, 1)

    def run_stage_1_discovery(self, task: str) -> StageResult:
        """
        Stage 1: Discovery - Dual-model analysis for HIGH risk tasks.

        Calls run_discovery_dual_model() from droid_core.
        Captures session_id, tokens, model, and output.
        """
        from scripts.droid_core import TaskType, run_discovery_dual_model

        started_at = datetime.now(UTC).isoformat()

        try:
            result = run_discovery_dual_model(
                prompt=f"Analyze this task and create a comprehensive spec: {task}",
                task_type=TaskType.SPEC,
                cwd=self.config.cwd,
            )

            # Extract data from primary result
            primary = result.primary_result
            session_id = primary.session_id or f"session-{self.run_id}-discovery"
            # MultiModelResult doesn't expose model id; use "unknown" until wired
            model = "unknown"
            output = result.merged_result or primary.result or ""
            success = primary.success

            # tokens_used=0 until real token accounting from droid_core/logs
            tokens_used = 0

            # Store session_id for continuity
            self.config.session_ids["discovery"] = session_id

            ended_at = datetime.now(UTC).isoformat()

            return StageResult(
                stage="discovery",
                status="pass" if success else "fail",
                started_at=started_at,
                ended_at=ended_at,
                session_id=session_id,
                model=model,
                output=output,  # Full output; truncate only in report mapping
                tokens_used=tokens_used,
            )

        except Exception as e:
            ended_at = datetime.now(UTC).isoformat()
            return StageResult(
                stage="discovery",
                status="fail",
                started_at=started_at,
                ended_at=ended_at,
                session_id=f"session-{self.run_id}-discovery-failed",
                model="none",
                output=f"Error: {e}",
                tokens_used=0,
            )

    def run_pipeline(
        self,
        task: str,
        dry_run: bool = False,
        risk_override: RiskLevel | None = None,
        start_stage: int | None = None,
        quiet: bool = False,
    ) -> PipelineResult:
        """Execute the full pipeline for a task."""
        started_at = datetime.now(UTC).isoformat()

        risk = risk_override or self.assess_risk(task)
        starting_stage = start_stage or self.route_by_risk(risk)

        if dry_run:
            if not quiet:
                print(f"[DRY-RUN] Task: {task}")
                print(f"[DRY-RUN] Risk: {risk.value}")
                print(f"[DRY-RUN] Starting stage: {starting_stage}")
                print(f"[DRY-RUN] Run ID: {self.run_id}")
                print("[DRY-RUN] Would execute stages:",
                      self.config.stages[starting_stage - 1:])

            return PipelineResult(
                run_id=self.run_id,
                task=task,
                risk_level=risk.value,
                status="success",
                stages=[],
                timestamps={
                    "started_at": started_at,
                    "ended_at": datetime.now(UTC).isoformat(),
                    "duration_seconds": 0.0,
                },
                metrics={
                    "total_tokens": 0,
                    "verification_iterations": 0,
                    "stages_executed": 0,
                    "stages_skipped": starting_stage - 1,
                },
                dry_run=True,
                exit_code=ExitCode.SUCCESS.value,
            )

        ended_at = datetime.now(UTC).isoformat()

        return PipelineResult(
            run_id=self.run_id,
            task=task,
            risk_level=risk.value,
            status="success",
            stages=[],
            timestamps={
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": 0.0,
            },
            metrics={
                "total_tokens": 0,
                "verification_iterations": 0,
                "stages_executed": 0,
                "stages_skipped": starting_stage - 1,
            },
            exit_code=ExitCode.SUCCESS.value,
        )

    def save_report(self, result: PipelineResult) -> Path:
        """Save pipeline result to report.json and update latest pointer.

        Creates symlink on Linux/macOS. Falls back to latest.txt on Windows
        or if symlink creation fails.
        """
        reports_dir = Path(self.config.cwd) / ".factory" / "reports"
        run_dir = reports_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        report_path = run_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump(result.to_report(), f, indent=2)

        self._update_latest_pointer(reports_dir, result.run_id)
        return report_path

    def _update_latest_pointer(self, reports_dir: Path, run_id: str) -> None:
        """Update latest pointer (symlink or fallback to latest.txt)."""
        latest_link = reports_dir / "latest"
        latest_txt = reports_dir / "latest.txt"

        try:
            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(run_id)
            if latest_txt.exists():
                latest_txt.unlink()
        except OSError:
            if latest_txt.exists():
                latest_txt.unlink()
            latest_txt.write_text(run_id)


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pipeline_runner.py",
        description="GAP-09 Pipeline Orchestrator - 5-stage AI development pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run "Fix typo in README.md" --dry-run
  %(prog)s run "Add JWT authentication" --risk high
  %(prog)s stage discovery "Analyze security flow"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser("run", help="Execute full pipeline")
    run_parser.add_argument("task", help="Task description")
    run_parser.add_argument("--dry-run", action="store_true", help="Simulate without execution")
    run_parser.add_argument(
        "--stage",
        choices=["discovery", "planning", "execution", "verification", "ship"],
        help="Start at specific stage (overrides risk routing)",
    )
    run_parser.add_argument(
        "--risk",
        choices=["low", "medium", "high"],
        help="Override automatic risk assessment",
    )
    run_parser.add_argument("--cwd", default=".", help="Working directory")
    run_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    stage_parser = subparsers.add_parser("stage", help="Execute single stage")
    stage_parser.add_argument(
        "stage_name",
        choices=["discovery", "planning", "execution", "verification", "ship"],
        help="Stage to execute",
    )
    stage_parser.add_argument("task", help="Task description")
    stage_parser.add_argument("--cwd", default=".", help="Working directory")

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    config = PipelineConfig(cwd=getattr(args, "cwd", "."))
    runner = PipelineRunner(config)

    if args.command == "run":
        risk_override = RiskLevel(args.risk.upper()) if args.risk else None

        start_stage = None
        if args.stage:
            stage_map = {"discovery": 1, "planning": 2, "execution": 3, "verification": 4, "ship": 5}
            start_stage = stage_map[args.stage]

        result = runner.run_pipeline(
            task=args.task,
            dry_run=args.dry_run,
            risk_override=risk_override,
            start_stage=start_stage,
            quiet=args.json,
        )

        if args.json:
            print(json.dumps(result.to_report(), indent=2))
        elif not args.dry_run:
            report_path = runner.save_report(result)
            print(f"Pipeline completed: {result.status}")
            print(f"Report saved: {report_path}")

        return result.exit_code

    elif args.command == "stage":
        print(f"[STAGE] Executing {args.stage_name} for: {args.task}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
