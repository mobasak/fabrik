#!/usr/bin/env python3
# RETIRED 2026-07-19 — Kilo CLI stack retired (operator directive: LLM access = Claude Max OAuth + OpenRouter only). Zero runtime callers; kept for history — do not use.
"""
Kilo Dispatch — Cascade-to-Kilo CLI Bridge

Builds a complete prompt (AGENTS-compact.md + selective rule packs + template
+ task) and dispatches it to a Kilo CLI agent. Designed to be called by
Windsurf Cascade via the /kilo workflow.

Rule packs are loaded selectively based on project type (from project.yaml)
using PACK_MAPPING, plus a TESTING overlay (always) and optional --packs CLI
overlays. Total rule content is capped at 40 lines.

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

Workflow Doc: docs/archive/KILO_DISPATCH_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

# ─── Exceptions ───────────────────────────────────────────────────────────────


class FabrikRootNoPacksError(Exception):
    """Raised when Kilo targets the Fabrik monorepo root without explicit --packs."""


# ─── Paths ────────────────────────────────────────────────────────────────────

FABRIK_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = Path.home() / ".traycer" / "cli-agents"
TEMPLATES_DIR = Path.home() / ".traycer" / "prompt-templates"

# ─── Pack Registry & Mapping ──────────────────────────────────────────────────
# Pack ID → rule file path (relative to project .windsurf/rules/)
PACK_REGISTRY: dict[str, str] = {
    "PY_CORE": "core/10-python.md",
    "NODE_CORE": "core/12-node.md",
    "API_CONTRACTS": "core/15-api-contracts.md",
    "TS_CORE": "core/20-typescript.md",
    "DATA_PG": "core/25-data-postgres.md",
    "OPS": "core/30-ops.md",
    "SECURITY": "core/35-security-auth.md",
    "DOCUMENTATION": "core/40-documentation.md",
    "DOCUSAURUS": "core/42-docusaurus.md",
    "TESTING": "core/45-testing-strategy.md",
    "CODE_REVIEW": "core/50-code-review.md",
    "OBSERVABILITY": "core/55-observability.md",
    "RESILIENCE": "core/58-resilience.md",
    "RAG_SEARCH": "core/65-rag-search.md",
    "RAG_CHUNKING": "core/66-rag-chunking.md",
    "FILE_API": "core/67-file-api.md",
    "WORKERS": "core/75-workers-jobs.md",
    "GPU_WORKERS": "core/76-gpu-workers.md",
    "PAYMENTS": "core/85-payments-billing.md",
    "EMAIL_TEMPLATES": "core/86-email-templates.md",
    "DESIGN_SYSTEM": "core/ocoron-design-system.md",
    "TOJLO_DESIGN": "core/tojlo-design-system.md",
    "SAAS_UI": "saas/60-saas-ui.md",
    "SAAS_LAUNCH": "saas/88-saas-launch-checklist.md",
    "ABUSE_DETECTION": "saas/87-abuse-detection.md",
    "MULTI_TENANT": "saas/95-multi-tenant-saas.md",
    "MOBILE_UI": "mobile-app/80-mobile.md",
    "MOBILE_BILLING": "mobile-app/81-mobile-billing.md",
    "MOBILE_LAUNCH": "mobile-app/89-mobile-launch-checklist.md",
    "MOBILE_DESIGN": "mobile-app/ocoron-mobile-design-system.md",
    "TOJLO_MOBILE_DESIGN": "mobile-app/tojlo-mobile-design-system.md",
    "CHROME_MV3": "chrome-ext/70-chrome-ext.md",
    "DESKTOP_APP": "desktop-app/72-desktop.md",
}

# Project type → default pack IDs (11 entries, mirrors AGENTS.md)
PACK_MAPPING: dict[str, list[str]] = {
    "python-api": ["PY_CORE"],
    "node-api": ["NODE_CORE"],
    "saas-skeleton": ["TS_CORE", "SAAS_UI", "DESIGN_SYSTEM"],
    "chrome-extension": ["PY_CORE", "TS_CORE", "CHROME_MV3", "DESIGN_SYSTEM"],
    "mobile-app": ["TS_CORE", "MOBILE_UI", "MOBILE_BILLING", "MOBILE_DESIGN"],
    "desktop-app": ["NODE_CORE", "TS_CORE", "DESKTOP_APP", "DESIGN_SYSTEM"],
    "file-api": ["NODE_CORE", "FILE_API"],
    "file-worker": ["PY_CORE", "WORKERS"],
    "wordpress": ["TS_CORE", "DESIGN_SYSTEM"],
    "docusaurus": ["DOCUSAURUS", "DESIGN_SYSTEM"],
    "static-site": ["TS_CORE", "SAAS_UI", "DESIGN_SYSTEM"],
}

# Universal overlay — always injected
TESTING_OVERLAY = "TESTING"

# Max total lines of rule content injected into prompt
MAX_RULE_LINES = 40

# Max lines extracted per pack
MAX_LINES_PER_PACK = 6


def _is_fabrik_root(project_dir: Path) -> bool:
    """Return True if *project_dir* is the Fabrik monorepo root.

    Detection: exact path comparison against FABRIK_ROOT (derived from
    this script's location).  Scaffolded child projects — even those
    containing AGENTS.md — are never matched.
    """
    return project_dir.resolve() == FABRIK_ROOT


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

log = logging.getLogger("kilo_dispatch")


def _extract_rule_lines(filepath: Path, max_lines: int = MAX_LINES_PER_PACK) -> list[str]:
    """Extract up to *max_lines* enforceable content lines from a rule file.

    Skips: YAML frontmatter, headings (#), blank lines, code-fence blocks,
    table rows starting with |, and lines that are just '---' separators.
    """
    if not filepath.exists():
        return []

    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_frontmatter = False
    frontmatter_seen = False
    in_code_block = False
    extracted: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Toggle YAML frontmatter (first --- opens, second --- closes)
        if stripped == "---" and not in_code_block:
            if not frontmatter_seen:
                in_frontmatter = not in_frontmatter
                if not in_frontmatter:
                    frontmatter_seen = True
            continue
        if in_frontmatter:
            continue

        # Toggle code blocks
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Skip blank lines, headings, table rows, activation/purpose meta lines
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("|"):
            continue
        if stripped.startswith("**Activation:"):
            continue
        if stripped.startswith("**Purpose:"):
            continue
        if stripped.startswith("**Note:"):
            continue

        extracted.append(stripped)
        if len(extracted) >= max_lines:
            break

    return extracted


def _resolve_packs(
    project_dir: Path, extra_packs: list[str] | None = None
) -> tuple[list[str], list[str]]:
    """Determine type-default and overlay pack IDs for a project.

    Returns (type_default_ids, overlay_ids).  TESTING is always an overlay.
    """
    project_yaml = project_dir / "project.yaml"
    type_defaults: list[str] = []

    if project_yaml.exists():
        try:
            meta = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
            project_type = (meta or {}).get("type", "")
        except Exception as exc:
            log.warning("Failed to parse project.yaml: %s", exc)
            project_type = ""

        if project_type and project_type in PACK_MAPPING:
            type_defaults = list(PACK_MAPPING[project_type])
        elif project_type:
            log.warning(
                "Unknown project type '%s' in project.yaml — loading AGENTS-compact.md only",
                project_type,
            )
    else:
        if _is_fabrik_root(project_dir):
            # Validate: --packs must be present AND resolve to at least one valid pack
            valid_user_packs = [
                p.strip().upper() for p in (extra_packs or []) if p.strip().upper() in PACK_REGISTRY
            ]
            if not valid_user_packs:
                raise FabrikRootNoPacksError(
                    f"No project.yaml in Fabrik root ({project_dir}). "
                    "Fabrik-root Kilo runs require explicit --packs with "
                    "valid pack IDs.\n\n"
                    "  Example:\n"
                    "    python scripts/kilo_dispatch.py \\.\n"
                    "        --agent <agent> --task <task> \\.\n"
                    "        --packs PY_CORE,TESTING\n\n"
                    "  Available packs: " + ", ".join(sorted(PACK_REGISTRY.keys()))
                )
        log.warning("No project.yaml found in %s — loading AGENTS-compact.md only", project_dir)

    # Build overlays: TESTING (always) + CLI --packs
    overlays: list[str] = []
    if TESTING_OVERLAY not in type_defaults:
        overlays.append(TESTING_OVERLAY)

    for pack_id in extra_packs or []:
        pack_id = pack_id.strip().upper()
        if pack_id and pack_id not in type_defaults and pack_id not in overlays:
            if pack_id in PACK_REGISTRY:
                overlays.append(pack_id)
            else:
                log.warning("Unknown pack ID '%s' from --packs — skipping", pack_id)

    return type_defaults, overlays


def load_project_context(project_dir: Path, extra_packs: list[str] | None = None) -> str:
    """Load AGENTS-compact.md and selectively loaded rule packs from the project.

    Rule selection: project.yaml type → PACK_MAPPING defaults + TESTING overlay
    + any --packs CLI overlays.  Total rule content capped at MAX_RULE_LINES;
    overlays are dropped first if the cap is exceeded.
    """
    sections: list[str] = []

    # AGENTS-compact.md only — no AGENTS.md fallback
    agents_path = project_dir / "AGENTS-compact.md"
    if agents_path.exists():
        sections.append(f"## AGENTS-compact.md\n\n{agents_path.read_text(encoding='utf-8')}")

    # Resolve packs
    type_defaults, overlays = _resolve_packs(project_dir, extra_packs)
    rules_dir = project_dir / ".windsurf" / "rules"

    # Load rule content: type defaults first, then overlays
    pack_blocks: list[tuple[str, list[str], bool]] = []  # (pack_id, lines, is_overlay)

    for pack_id in type_defaults:
        filename = PACK_REGISTRY.get(pack_id)
        if not filename:
            log.warning("Pack '%s' not in PACK_REGISTRY — skipping", pack_id)
            continue
        rule_path = rules_dir / filename
        if not rule_path.exists():
            log.warning("Rule file '%s' for pack %s not found — skipping", filename, pack_id)
            continue
        lines = _extract_rule_lines(rule_path)
        if lines:
            pack_blocks.append((pack_id, lines, False))

    for pack_id in overlays:
        filename = PACK_REGISTRY.get(pack_id)
        if not filename:
            continue
        rule_path = rules_dir / filename
        if not rule_path.exists():
            log.warning("Rule file '%s' for overlay %s not found — skipping", filename, pack_id)
            continue
        lines = _extract_rule_lines(rule_path)
        if lines:
            pack_blocks.append((pack_id, lines, True))

    # Enforce 40-line cap: drop overlays from end first
    total_lines = sum(len(lines) for _, lines, _ in pack_blocks)
    if total_lines > MAX_RULE_LINES:
        # Drop overlay blocks from the end until under cap
        while total_lines > MAX_RULE_LINES and pack_blocks:
            last_id, last_lines, is_overlay = pack_blocks[-1]
            if is_overlay:
                pack_blocks.pop()
                total_lines -= len(last_lines)
                log.warning(
                    "Dropped overlay pack %s to stay within %d-line cap", last_id, MAX_RULE_LINES
                )
            else:
                break  # Don't drop type defaults

    # Format rule packs into prompt section
    if pack_blocks:
        rule_section_parts = ["## Rule Packs Active\n"]
        for pack_id, lines, _ in pack_blocks:
            filename = PACK_REGISTRY.get(pack_id, "")
            rule_section_parts.append(f"[{pack_id}] .windsurf/rules/{filename}")
            for line in lines:
                rule_section_parts.append(f"- {line}")
        sections.append("\n".join(rule_section_parts))

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


def build_prompt(
    task: str,
    template_key: str,
    project_dir: Path,
    extra_packs: list[str] | None = None,
) -> str:
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
    project_context = load_project_context(project_dir, extra_packs=extra_packs)

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
    parser.add_argument(
        "--packs",
        default="",
        help="Comma-separated overlay pack IDs (e.g. DATA_PG,SECURITY)",
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

    # Parse extra packs
    extra_packs = [p for p in args.packs.split(",") if p.strip()] if args.packs else None

    # Build prompt
    try:
        prompt = build_prompt(task, args.template, project_dir, extra_packs=extra_packs)
    except FabrikRootNoPacksError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

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
