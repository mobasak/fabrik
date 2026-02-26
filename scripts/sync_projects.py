#!/usr/bin/env python3
"""
Sync /opt/* projects into /opt/fabrik/docs/BUSINESS_MODEL.md

Triggers:
- Post-scaffold: fabrik scaffold completion
- Manual: python scripts/sync_projects.py

Scans /opt/* (excluding _* prefixes) and updates AUTO-GENERATED:PROJECTS block
in /opt/fabrik/docs/BUSINESS_MODEL.md with project catalog.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class Project:
    """Project metadata"""

    name: str
    path: Path
    purpose: str
    stack: str
    status: str
    url: str | None
    category: str
    scaffold_status: str


def scan_projects(root: Path = Path("/opt")) -> list[Project]:
    """Scan /opt/* excluding _* prefixes"""
    projects = []

    for project_path in sorted(root.iterdir()):
        if not project_path.is_dir():
            continue
        if project_path.name.startswith("_"):
            continue
        if project_path.name == "fabrik":
            continue  # Skip fabrik itself

        project = extract_metadata(project_path)
        if project:
            projects.append(project)

    return projects


def extract_metadata(path: Path) -> Project | None:
    """Extract metadata from project directory"""
    name = path.name

    # Extract purpose from README.md
    purpose = extract_purpose(path)
    if not purpose:
        purpose = "No description available"

    # Detect stack from compose.yaml or package files
    stack = detect_stack(path)

    # Detect deployment status and URL
    status, url = detect_deployment(name)

    # Categorize project
    category = categorize_project(path, status)

    # Check scaffold compliance
    scaffold_status = check_scaffold_compliance(path)

    return Project(
        name=name,
        path=path,
        purpose=purpose,
        stack=stack,
        status=status,
        url=url,
        category=category,
        scaffold_status=scaffold_status,
    )


def extract_purpose(path: Path) -> str | None:
    """Extract purpose from README.md Overview section"""
    readme = path / "README.md"
    if not readme.exists():
        return None

    try:
        content = readme.read_text(encoding="utf-8")

        # Try to find "## Overview" section
        match = re.search(r"##\s+Overview\s*\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if match:
            overview = match.group(1).strip()
            # Take first line or first 100 chars
            first_line = overview.split("\n")[0].strip()
            if len(first_line) > 100:
                first_line = first_line[:97] + "..."
            return first_line

        # Fallback: first paragraph after title
        lines = content.split("\n")
        for line in lines:
            if line.strip() and not line.startswith("#"):
                purpose = line.strip()
                if len(purpose) > 100:
                    purpose = purpose[:97] + "..."
                return purpose

    except Exception:
        pass

    return None


def detect_stack(path: Path) -> str:
    """Detect stack from compose.yaml, pyproject.toml, package.json"""
    stack_parts = []

    # Check compose.yaml for services
    compose_file = path / "compose.yaml"
    if compose_file.exists():
        try:
            with open(compose_file) as f:
                compose_data = yaml.safe_load(f)
                services = compose_data.get("services", {})

                # Detect common services
                if "postgres" in services or "db" in services:
                    stack_parts.append("PostgreSQL")
                if "redis" in services:
                    stack_parts.append("Redis")

        except Exception:
            pass

    # Check for Python (pyproject.toml or requirements.txt)
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        # Check for FastAPI
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "fastapi" in content.lower():
                    stack_parts.insert(0, "FastAPI")
                elif "flask" in content.lower():
                    stack_parts.insert(0, "Flask")
                else:
                    stack_parts.insert(0, "Python")
            except Exception:
                stack_parts.insert(0, "Python")
        else:
            stack_parts.insert(0, "Python")

    # Check for Node.js (package.json)
    elif (path / "package.json").exists():
        try:
            with open(path / "package.json") as f:
                pkg = yaml.safe_load(f)
                deps = pkg.get("dependencies", {})
                if "express" in deps:
                    stack_parts.insert(0, "Express")
                elif "fastify" in deps:
                    stack_parts.insert(0, "Fastify")
                else:
                    stack_parts.insert(0, "Node.js")
        except Exception:
            stack_parts.insert(0, "Node.js")

    # Check for WordPress
    elif (path / "wp-config.php").exists():
        stack_parts.insert(0, "WordPress")

    if not stack_parts:
        return "Unknown"

    return " + ".join(stack_parts)


def detect_deployment(project_name: str) -> tuple[str, str | None]:
    """Detect if project is deployed (simple heuristic for now)"""
    # This is a placeholder - in full implementation, would query Coolify API
    # For now, use simple heuristics

    # Known production URLs
    production_urls = {
        "captcha": "https://captcha.vps1.ocoron.com",
        "dns-manager": "https://dns.vps1.ocoron.com",
        "file-api": "https://files-api.vps1.ocoron.com",
        "translator": "https://translator.vps1.ocoron.com",
        "youtube": "Multi-tenant SaaS",
    }

    if project_name in production_urls:
        return "✅ Production", production_urls[project_name]

    return "🔨 Development", None


def categorize_project(path: Path, status: str) -> str:
    """Categorize project based on completeness"""
    has_compose = (path / "compose.yaml").exists()
    has_readme = (path / "README.md").exists()
    has_code = (path / "src").exists() or (path / "app").exists()

    if status == "✅ Production":
        return "production"
    elif has_compose and has_code:
        return "active"
    elif has_readme or (path / "docs").exists():
        return "planning"
    else:
        return "shell"


def check_scaffold_compliance(path: Path) -> str:
    """Check if project uses latest Fabrik scaffold"""
    # Simple check: does .windsurfrules exist and is it a symlink?
    windsurfrules = path / ".windsurfrules"

    if not windsurfrules.exists():
        return "❌ No scaffold"
    elif windsurfrules.is_symlink():
        return "✅ Current"
    else:
        return "⚠️ Needs update"


def generate_catalog_markdown(projects: list[Project]) -> str:
    """Generate markdown for project catalog"""
    # Group by category
    production = [p for p in projects if p.category == "production"]
    active = [p for p in projects if p.category == "active"]
    planning = [p for p in projects if p.category == "planning"]
    shell = [p for p in projects if p.category == "shell"]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(projects)

    md = f"<!-- Last synced: {timestamp} -->\n"
    md += f"<!-- Total projects: {total} -->\n\n"

    # Production services
    if production:
        md += f"### Production Services ({len(production)} projects)\n\n"
        md += "| Project | Purpose | Stack | Status | URL | Scaffold Status |\n"
        md += "|---------|---------|-------|--------|-----|------------------|\n"
        for p in sorted(production, key=lambda x: x.name):
            url_display = p.url if p.url else "-"
            md += f"| **{p.name}** | {p.purpose} | {p.stack} | {p.status} | {url_display} | {p.scaffold_status} |\n"
        md += "\n"

    # Active development
    if active:
        md += f"### Active Development ({len(active)} projects)\n\n"
        md += "| Project | Purpose | Stack | Status | URL | Scaffold Status |\n"
        md += "|---------|---------|-------|--------|-----|------------------|\n"
        for p in sorted(active, key=lambda x: x.name):
            url_display = p.url if p.url else "-"
            md += f"| **{p.name}** | {p.purpose} | {p.stack} | {p.status} | {url_display} | {p.scaffold_status} |\n"
        md += "\n"

    # Planning/Research
    if planning:
        md += f"### Planning/Research ({len(planning)} projects)\n\n"
        md += "| Project | Purpose | Stack | Status | URL | Scaffold Status |\n"
        md += "|---------|---------|-------|--------|-----|------------------|\n"
        for p in sorted(planning, key=lambda x: x.name):
            url_display = p.url if p.url else "-"
            md += f"| **{p.name}** | {p.purpose} | {p.stack} | {p.status} | {url_display} | {p.scaffold_status} |\n"
        md += "\n"

    # Shell projects
    if shell:
        md += f"### Shell Projects ({len(shell)} projects)\n\n"
        md += "| Project | Purpose | Stack | Status | URL | Scaffold Status |\n"
        md += "|---------|---------|-------|--------|-----|------------------|\n"
        for p in sorted(shell, key=lambda x: x.name):
            url_display = p.url if p.url else "-"
            md += f"| **{p.name}** | {p.purpose} | {p.stack} | {p.status} | {url_display} | {p.scaffold_status} |\n"
        md += "\n"

    return md


def update_business_model(catalog_md: str):
    """Update /opt/fabrik/docs/BUSINESS_MODEL.md AUTO-GENERATED block"""
    business_model_path = Path("/opt/fabrik/docs/BUSINESS_MODEL.md")

    if not business_model_path.exists():
        print(f"ERROR: {business_model_path} does not exist")
        return False

    content = business_model_path.read_text(encoding="utf-8")

    # Find AUTO-GENERATED block
    pattern = r"(<!-- AUTO-GENERATED:PROJECTS:START -->).*?(<!-- AUTO-GENERATED:PROJECTS:END -->)"
    replacement = f"\\1\n{catalog_md}\\2"

    if "AUTO-GENERATED:PROJECTS:START" not in content:
        # Block doesn't exist, add it at the end
        content += "\n\n---\n\n"
        content += "## Project Portfolio\n\n"
        content += "<!-- AUTO-GENERATED:PROJECTS:START -->\n"
        content += catalog_md
        content += "<!-- AUTO-GENERATED:PROJECTS:END -->\n"
    else:
        # Replace existing block
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    business_model_path.write_text(content, encoding="utf-8")
    print(f"✅ Updated {business_model_path}")
    return True


def main():
    """Main entry point"""
    print("📊 Scanning /opt/* projects...")

    projects = scan_projects()
    print(f"Found {len(projects)} projects")

    catalog_md = generate_catalog_markdown(projects)

    if update_business_model(catalog_md):
        print("✅ Project catalog synced successfully")
    else:
        print("❌ Failed to update BUSINESS_MODEL.md")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
