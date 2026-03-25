#!/usr/bin/env python3
"""
Kilo Dispatch — Cascade-to-Kilo CLI Bridge

Builds a complete prompt (AGENTS.md + rules + template + task) and dispatches
it to a Kilo CLI agent. Designed to be called by Windsurf Cascade via the
/kilo workflow.

Usage:
    # Dispatch a coding task
    python /opt/fabrik/scripts/kilo_dispatch.py \
        --agent "code&fix-1-opus46-max-o2500-ppd076.sh" \
        --task "Implement user authentication" \
        --project /opt/myproject

    # Dispatch a fix task
    python /opt/fabrik/scripts/kilo_dispatch.py \
        --agent "fixing-2-gemini31pro-max-o1200-ppd161.sh" \
        --task "Fix review findings" \
        --template fix \
        --project /opt/myproject

    # List available agents
    python /opt/fabrik/scripts/kilo_dispatch.py --list

    # Dry-run: show constructed prompt without running
    python /opt/fabrik/scripts/kilo_dispatch.py \
        --agent "coding-2-gpt54-max-o1500-ppd123.sh" \
        --task "Add health endpoint" --dry-run

    # Pass a plan file instead of inline task
    python /opt/fabrik/scripts/kilo_dispatch.py \
        --agent "code&fix-1-opus46-max-o2500-ppd076.sh" \
        --task-file docs/development/plans/my-plan.md \
        --template plan

Workflow Doc: docs/workflows/KILO_DISPATCH_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

AGENTS_DIR = Path.home() / ".traycer" / "cli-agents"
TEMPLATES_DIR = Path.home() / ".traycer" / "prompt-templates"

# Template mapping: role keyword → template file + placeholder name
TEMPLATE_MAP: dict[str, tuple[str, str]] = {
    "code": ("Coder-for-Plan-Mode.md", "{{userQuery}}"),
    "plan": ("Coder-for-Phased-Epic-Modes.md", "{{planMarkdown}}"),
    "fix": ("Fix-After-Review.md", "{{reviewComments}}"),
    "verify": ("Fix-After-Verification.md", "{{comments}}"),
}


# ─── Agent Discovery ─────────────────────────────────────────────────────────


def find_agent_script(name: str) -> Path | None:
    """Find agent script by exact name or prefix match."""
    # Exact match first
    exact = AGENTS_DIR / name
    if exact.exists():
        return exact

    # Prefix match (user can omit the .sh or the full ppd suffix)
    for script in sorted(AGENTS_DIR.glob("*.sh")):
        if script.name.startswith(name) or script.stem.startswith(name):
            return script
    return None


def list_agents() -> list[dict[str, str]]:
    """List available agents with parsed metadata."""
    agents = []
    for script in sorted(AGENTS_DIR.glob("*.sh")):
        # Parse: <role>-<priority>-<model>-<variant>-o<OUT>-ppd<PPD>.sh
        stem = script.stem
        parts = stem.split("-")

        # Role may contain & (e.g., code&fix)
        # Find the priority digit to split role from rest
        role_parts = []
        rest_parts = []
        found_priority = False
        for part in parts:
            if not found_priority and part.isdigit():
                found_priority = True
                rest_parts.append(part)
            elif found_priority:
                rest_parts.append(part)
            else:
                role_parts.append(part)

        role = "-".join(role_parts) if role_parts else "unknown"
        priority = rest_parts[0] if rest_parts else "?"

        # Extract cost and PPD from filename
        cost_str = ""
        ppd_str = ""
        for p in rest_parts:
            if p.startswith("o") and p[1:].isdigit():
                cost_val = int(p[1:]) / 100
                cost_str = f"${cost_val:.2f}/1M out"
            if p.startswith("ppd") and p[3:].isdigit():
                ppd_str = p[3:]

        agents.append(
            {
                "name": script.name,
                "role": role,
                "priority": priority,
                "cost": cost_str,
                "ppd": ppd_str,
            }
        )
    return agents


# ─── Prompt Construction ─────────────────────────────────────────────────────


def load_project_context(project_dir: Path) -> str:
    """Load AGENTS.md and .windsurf/rules/ from the project."""
    sections = []

    # AGENTS.md (or AGENTS-compact.md)
    for agents_name in ("AGENTS-compact.md", "AGENTS.md"):
        agents_path = project_dir / agents_name
        if agents_path.exists():
            content = agents_path.read_text(encoding="utf-8")
            sections.append(f"## {agents_name}\n\n{content}")
            break

    # .windsurf/rules/
    rules_dir = project_dir / ".windsurf" / "rules"
    if rules_dir.exists():
        rule_files = sorted(rules_dir.glob("*.md"))
        if rule_files:
            rules_content = []
            for rf in rule_files:
                rules_content.append(f"### {rf.name}\n\n{rf.read_text(encoding='utf-8')}")
            sections.append("## .windsurf/rules/\n\n" + "\n\n---\n\n".join(rules_content))

    return "\n\n---\n\n".join(sections)


def load_template(template_key: str) -> tuple[str, str]:
    """Load prompt template and return (content, placeholder_name)."""
    if template_key not in TEMPLATE_MAP:
        print(f"ERROR: Unknown template '{template_key}'. Available: {list(TEMPLATE_MAP.keys())}")
        sys.exit(1)

    filename, placeholder = TEMPLATE_MAP[template_key]
    template_path = TEMPLATES_DIR / filename

    if not template_path.exists():
        print(f"WARNING: Template not found: {template_path}", file=sys.stderr)
        # Fallback: just wrap the task
        return f"## Task\n\n{placeholder}", placeholder

    return template_path.read_text(encoding="utf-8"), placeholder


def build_prompt(task: str, template_key: str, project_dir: Path) -> str:
    """Build the full prompt: project context + template + task."""
    # Load template
    template_content, placeholder = load_template(template_key)

    # Substitute the task into the template
    if placeholder in template_content:
        filled_template = template_content.replace(placeholder, task)
    else:
        # Template doesn't have the placeholder — append task
        filled_template = template_content + f"\n\n{task}"

    # Load project context
    project_context = load_project_context(project_dir)

    # Combine
    prompt = f"""# Kilo CLI Task — Dispatched by Cascade
Working directory: {project_dir}
Timestamp: {datetime.now().isoformat()}

---

# Project Context

{project_context}

---

# Task Instructions

{filled_template}
"""
    return prompt


# ─── Report Reading ──────────────────────────────────────────────────────────


def read_latest_report(project_dir: Path) -> str | None:
    """Read the latest Traycer report from the project."""
    report_path = project_dir / ".droid" / "traycer-reports" / "latest.md"
    if report_path.exists():
        return report_path.read_text(encoding="utf-8")
    return None


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kilo Dispatch — Cascade-to-Kilo CLI Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --agent "coding-2-gpt54" --task "Add health endpoint"
  %(prog)s --agent "code&fix-1-opus46" --task "Implement auth" --template code
  %(prog)s --agent "fixing-2-gemini31pro" --task-file review.md --template fix
  %(prog)s --agent "coding-3-gemini31pro" --task "Refactor DB layer" --dry-run
""",
    )
    parser.add_argument("--agent", help="Agent script name (exact or prefix match)")
    parser.add_argument("--task", help="Task description (inline)")
    parser.add_argument("--task-file", help="Task description from file")
    parser.add_argument(
        "--template",
        default="code",
        choices=list(TEMPLATE_MAP.keys()),
        help="Prompt template to use (default: code)",
    )
    parser.add_argument(
        "--project",
        default=os.getcwd(),
        help="Project directory (default: cwd)",
    )
    parser.add_argument(
        "--timeout", type=int, default=7200, help="Timeout in seconds (default: 7200)"
    )
    parser.add_argument("--list", action="store_true", help="List available agents")
    parser.add_argument("--dry-run", action="store_true", help="Show prompt, don't run")
    args = parser.parse_args()

    # List mode
    if args.list:
        agents = list_agents()
        if not agents:
            print(f"No agents found in {AGENTS_DIR}")
            return 1
        print(f"Available Kilo CLI agents ({AGENTS_DIR}):\n")
        for a in agents:
            ppd_label = f"  PPD:{a['ppd']}" if a["ppd"] else ""
            print(f"  #{a['priority']}  {a['role']:12s}  {a['cost']:16s}{ppd_label}")
            print(f"      {a['name']}")
        return 0

    # Validate
    if not args.agent:
        parser.error("--agent is required (or use --list)")
    if not args.task and not args.task_file:
        parser.error("--task or --task-file is required")

    # Find agent
    agent_script = find_agent_script(args.agent)
    if not agent_script:
        print(f"ERROR: Agent '{args.agent}' not found in {AGENTS_DIR}")
        print("Use --list to see available agents.")
        return 1

    # Load task
    if args.task_file:
        task_path = Path(args.task_file)
        if not task_path.exists():
            print(f"ERROR: Task file not found: {task_path}")
            return 1
        task = task_path.read_text(encoding="utf-8")
    else:
        task = args.task

    project_dir = Path(args.project).resolve()

    # Build prompt
    prompt = build_prompt(task, args.template, project_dir)

    # Dry-run mode
    if args.dry_run:
        print("═" * 70)
        print("DRY RUN — Prompt that would be sent to Kilo:")
        print("═" * 70)
        print(f"Agent:    {agent_script.name}")
        print(f"Project:  {project_dir}")
        print(f"Template: {args.template}")
        print(f"Timeout:  {args.timeout}s")
        print("─" * 70)
        print(prompt)
        print("─" * 70)
        print(f"Prompt size: {len(prompt):,} chars")
        return 0

    # Write prompt to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        prefix="kilo-dispatch-",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(prompt)
        prompt_tmp_path = tmp.name

    try:
        # Set up environment
        env = os.environ.copy()
        env["TRAYCER_PROMPT_TMP_FILE"] = prompt_tmp_path
        env["TRAYCER_TASK_ID"] = f"cascade-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        env["TRAYCER_WORKFLOW"] = "cascade-dispatch"
        env["TRAYCER_HANDOFF_TYPE"] = args.template
        env["KILO_TIMEOUT"] = str(args.timeout)

        # Print dispatch header
        print("╔══════════════════════════════════════════════════════════════╗")
        print(f"║  Kilo Dispatch → {agent_script.name[:44]:<44s} ║")
        print(f"║  Project: {str(project_dir)[:50]:<50s} ║")
        print(f"║  Template: {args.template:<49s} ║")
        print(f"║  Task ID: {env['TRAYCER_TASK_ID']:<50s} ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()

        # Run agent script — inherit stdio so TUI works
        result = subprocess.run(
            ["bash", str(agent_script)],
            cwd=str(project_dir),
            env=env,
        )

        # Post-execution: read report
        print()
        print("═" * 70)

        report = read_latest_report(project_dir)
        if report:
            print("📋 Kilo Report:")
            print("─" * 70)
            print(report)
            print("─" * 70)
        else:
            print("⚠️  No report found in .droid/traycer-reports/latest.md")

        print(f"Exit code: {result.returncode}")
        return result.returncode

    finally:
        # Clean up temp file
        try:
            os.unlink(prompt_tmp_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
