"""Helpers for the dev-tooling CLI commands (T3-03).

Three commands share this module so cli.py stays thin and the logic can be
unit-tested without invoking the full click harness:

- ``fabrik review`` (G-D3): bundle git diff + spec + preplan + resolved
  registrars into ``.fabrik/review/<ts>.md``.
- ``fabrik dev`` (G-I1): run ``docker compose -f compose.dev.yaml up`` in the
  project directory.
- ``fabrik logs --local`` (G-I2): tail docker compose logs for the local dev
  stack (sibling of the existing Loki-backed ``fabrik logs <service>``).

The module is self-contained — no orchestrator side effects, no driver
imports beyond pure ``resolve_applicability`` / ``format_resolved_summary``.
"""

from __future__ import annotations

import datetime as _dt
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import FABRIK_ROOT
from .orchestrator.infrastructure import format_resolved_summary, resolve_applicability

REVIEW_DIR = ".fabrik/review"
DEV_COMPOSE = "compose.dev.yaml"


@dataclass
class ReviewBundleStats:
    """Returned alongside the bundle text for human-friendly summary lines."""

    diff_lines: int
    spec_lines: int
    preplan_lines: int
    registrars_run: int
    registrars_skipped: int


def find_spec(project_dir: Path) -> Path | None:
    """Locate the spec for ``project_dir``.

    Resolution order:

    1. ``<project_dir>/specs/services/*.yaml`` — first match alphabetically.
       The ticket's "cwd-aware" path; intended for projects that carry their
       own spec locally.
    2. ``<FABRIK_ROOT>/specs/services/<project_dir.name>.yaml`` — the
       centralized location used today on this VPS (specs live in the fabrik
       repo, not in the per-service repos). Without this fallback,
       ``fabrik review`` would always miss the spec for deployed services
       (translator, file-api, image-broker, etc.) and skip the resolved-
       registrar section.

    Returns ``None`` if neither location yields a file.
    """
    local = sorted((project_dir / "specs" / "services").glob("*.yaml"))
    if local:
        return local[0]
    central = FABRIK_ROOT / "specs" / "services" / f"{project_dir.name}.yaml"
    return central if central.exists() else None


def _git_diff(project_dir: Path, since: str) -> str:
    """Capture the textual diff. Returns empty string if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "diff", since],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    return result.stdout


def build_review_bundle(
    project_dir: Path,
    since: str,
    spec_path: Path | None,
) -> tuple[str, ReviewBundleStats]:
    """Produce the markdown content for a review bundle.

    Sections (in order, all optional except header + diff):
        1. Header (ISO timestamp, project name)
        2. Diff (``git diff <since>`` output)
        3. Spec contents
        4. Resolved registrars (from ``resolve_applicability`` if a spec found)
        5. Preplan (docs/preplan.md if it exists)

    Returns the bundle text plus stats for the operator-facing summary lines.
    """
    diff_text = _git_diff(project_dir, since)
    diff_lines = diff_text.count("\n") if diff_text else 0

    spec_section = ""
    resolved_section = ""
    spec_lines = 0
    n_run = 0
    n_skip = 0

    if spec_path and spec_path.exists():
        spec_text = spec_path.read_text(encoding="utf-8")
        spec_lines = spec_text.count("\n")
        rel = (
            spec_path.relative_to(project_dir)
            if spec_path.is_relative_to(project_dir)
            else spec_path
        )
        spec_section = f"\n\n## Spec (`{rel}`)\n\n```yaml\n{spec_text}\n```"

        try:
            spec_dict = yaml.safe_load(spec_text) or {}
            resolved = resolve_applicability(spec_dict)
            n_run = sum(1 for runs, _ in resolved.values() if runs)
            n_skip = sum(1 for runs, _ in resolved.values() if not runs)
            resolved_section = (
                "\n\n## Resolved registrars\n\n```\n" + format_resolved_summary(resolved) + "\n```"
            )
        except Exception as e:
            resolved_section = f"\n\n## Resolved registrars\n\n_resolve failed: {e}_"

    preplan_section = ""
    preplan_lines = 0
    preplan_path = project_dir / "docs" / "preplan.md"
    if preplan_path.exists():
        preplan_text = preplan_path.read_text(encoding="utf-8")
        preplan_lines = preplan_text.count("\n")
        preplan_section = f"\n\n## Preplan (`docs/preplan.md`)\n\n{preplan_text}"

    ts = _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")
    diff_block = diff_text if diff_text.strip() else "(no changes)"
    body = (
        f"# Review bundle — {project_dir.name}\n"
        f"_Generated {ts} via `fabrik review --since {since}`_\n\n"
        f"## Diff (`git diff {since}`)\n\n"
        f"```diff\n{diff_block}\n```" + spec_section + preplan_section + resolved_section + "\n"
    )
    stats = ReviewBundleStats(
        diff_lines=diff_lines,
        spec_lines=spec_lines,
        preplan_lines=preplan_lines,
        registrars_run=n_run,
        registrars_skipped=n_skip,
    )
    return body, stats


def save_review_bundle(
    project_dir: Path,
    content: str,
    out: Path | None = None,
) -> Path:
    """Write the bundle to disk; default location ``.fabrik/review/<ts>.md``."""
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        return out
    ts = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d-%H%M%S")
    review_dir = project_dir / REVIEW_DIR
    review_dir.mkdir(parents=True, exist_ok=True)
    target = review_dir / f"{ts}.md"
    target.write_text(content, encoding="utf-8")
    return target


def _has_dev_compose(project_dir: Path) -> Path | None:
    """Return the ``compose.dev.yaml`` path if present in ``project_dir``."""
    candidate = project_dir / DEV_COMPOSE
    return candidate if candidate.exists() else None


def run_dev_compose(
    project_dir: Path,
    detach: bool,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> int:
    """Run ``docker compose -f compose.dev.yaml up [-d]`` in ``project_dir``.

    Returns the subprocess exit code, or -1 if ``compose.dev.yaml`` is missing.
    ``runner`` is injectable so tests can mock the docker invocation.
    """
    compose = _has_dev_compose(project_dir)
    if compose is None:
        return -1
    args = ["docker", "compose", "-f", str(compose), "up"]
    if detach:
        args.append("-d")
    proc = runner(args, cwd=str(project_dir), check=False)
    return proc.returncode


def run_local_logs(
    project_dir: Path,
    service: str | None,
    follow: bool,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> int:
    """Run ``docker compose -f compose.dev.yaml logs [-f] [<service>]``.

    Returns the subprocess exit code, or -1 if ``compose.dev.yaml`` is missing.
    """
    compose = _has_dev_compose(project_dir)
    if compose is None:
        return -1
    args = ["docker", "compose", "-f", str(compose), "logs"]
    if follow:
        args.append("-f")
    if service:
        args.append(service)
    proc = runner(args, cwd=str(project_dir), check=False)
    return proc.returncode
