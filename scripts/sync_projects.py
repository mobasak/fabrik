#!/usr/bin/env python3
"""
Sync /opt/* projects into data/projects.yaml + docs/BUSINESS_MODEL.md

Source of truth: each project's project.yaml (created by fabrik scaffold).
For projects without project.yaml, metadata is auto-detected from filesystem.

Triggers:
- Post-scaffold: called automatically by scaffold.py
- Manual: python scripts/sync_projects.py
- CLI: fabrik scan

Outputs:
- /opt/fabrik/data/projects.yaml  (aggregated registry, machine-readable)
- /opt/fabrik/docs/BUSINESS_MODEL.md  (AUTO-GENERATED:PROJECTS block, human-readable)

Workflow Doc: docs/workflows/SYNC_PROJECTS_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

FABRIK_ROOT = Path("/opt/fabrik")
DEFAULT_EXCLUDES = {"_*", ".*", "fabrik", "__pycache__", "venv", "google", "containerd"}


@dataclass
class Project:
    """Project metadata — merged from project.yaml + auto-detection."""

    name: str
    path: str
    type: str = "unknown"
    description: str = "No description available"
    created: str = ""
    status: str = "development"
    category: str = "planning"
    url: str | None = None
    domain: str | None = None
    ports: list[int] = field(default_factory=list)
    stack: str = "Unknown"
    scaffold_status: str = "❌ No scaffold"
    # Extended
    external_systems: list[str] = field(default_factory=list)
    monthly_cost: float = 0
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    has_user_guide: bool = False

    def to_registry_dict(self) -> dict:
        """Serialize for data/projects.yaml."""
        d: dict = {
            "path": self.path,
            "type": self.type,
            "description": self.description,
            "status": self.status,
            "category": self.category,
            "stack": self.stack,
            "scaffold_status": self.scaffold_status,
        }
        if self.created:
            d["created"] = self.created
        if self.url:
            d["url"] = self.url
        if self.domain:
            d["domain"] = self.domain
        if self.ports:
            d["ports"] = self.ports
        if self.external_systems:
            d["external_systems"] = self.external_systems
        if self.monthly_cost:
            d["monthly_cost"] = self.monthly_cost
        if self.dependencies:
            d["dependencies"] = self.dependencies
        if self.tags:
            d["tags"] = self.tags
        d["has_user_guide"] = self.has_user_guide
        return d


def _is_excluded(name: str) -> bool:
    """Check if project name matches exclusion patterns."""
    import fnmatch

    return any(fnmatch.fnmatch(name, p) for p in DEFAULT_EXCLUDES)


def scan_projects(root: Path = Path("/opt")) -> list[Project]:
    """Scan /opt/* and build project list from project.yaml + auto-detection."""
    projects = []

    for project_path in sorted(root.iterdir()):
        if not project_path.is_dir():
            continue
        if _is_excluded(project_path.name):
            continue

        project = _build_project(project_path)
        projects.append(project)

    return projects


def _build_project(path: Path) -> Project:
    """Build Project from project.yaml (if exists) merged with auto-detected data."""
    name = path.name

    # Start with auto-detected defaults
    project = Project(
        name=name,
        path=str(path),
        description=_extract_purpose(path) or "No description available",
        stack=_detect_stack(path),
        scaffold_status=_check_scaffold(path),
    )

    # Read project.yaml if it exists — overrides auto-detected fields
    project_yaml = path / "project.yaml"
    if project_yaml.exists():
        try:
            data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                for key in (
                    "type",
                    "description",
                    "created",
                    "status",
                    "category",
                    "url",
                    "domain",
                    "ports",
                    "external_systems",
                    "monthly_cost",
                    "dependencies",
                    "tags",
                    "has_user_guide",
                ):
                    if key in data and data[key] is not None:
                        setattr(project, key, data[key])
        except Exception:
            pass  # Malformed YAML — use auto-detected

    # Auto-categorize if project.yaml didn't explicitly set category
    has_explicit_category = False
    if project_yaml.exists():
        try:
            pdata = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
            has_explicit_category = "category" in pdata
        except Exception:
            pass
    if not has_explicit_category:
        project.category = _auto_categorize(path, project.status)

    # Status emoji for display
    if project.status == "production":
        project.status = "✅ Production"
    elif project.status not in ("✅ Production",):
        project.status = "🔨 Development"

    return project


def _extract_purpose(path: Path) -> str | None:
    """Extract purpose from README.md Overview section."""
    readme = path / "README.md"
    if not readme.exists():
        return None
    try:
        content = readme.read_text(encoding="utf-8")
        match = re.search(r"##\s+Overview\s*\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if match:
            first_line = match.group(1).strip().split("\n")[0].strip()
            return first_line[:97] + "..." if len(first_line) > 100 else first_line

        for line in content.split("\n"):
            if line.strip() and not line.startswith("#"):
                purpose = line.strip()
                return purpose[:97] + "..." if len(purpose) > 100 else purpose
    except Exception:
        pass
    return None


def _detect_stack(path: Path) -> str:
    """Detect stack from compose.yaml, pyproject.toml, package.json."""
    stack_parts = []

    compose_file = path / "compose.yaml"
    if compose_file.exists():
        try:
            data = yaml.safe_load(compose_file.read_text()) or {}
            services = data.get("services", {})
            if "postgres" in services or "db" in services:
                stack_parts.append("PostgreSQL")
            if "redis" in services:
                stack_parts.append("Redis")
        except Exception:
            pass

    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
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
    elif (path / "package.json").exists():
        try:
            pkg = yaml.safe_load((path / "package.json").read_text()) or {}
            deps = pkg.get("dependencies", {})
            if "express" in deps:
                stack_parts.insert(0, "Express")
            elif "fastify" in deps:
                stack_parts.insert(0, "Fastify")
            else:
                stack_parts.insert(0, "Node.js")
        except Exception:
            stack_parts.insert(0, "Node.js")
    elif (path / "wp-config.php").exists():
        stack_parts.insert(0, "WordPress")

    if not stack_parts:
        # Fallback: derive stack from project.yaml type field
        project_yaml = path / "project.yaml"
        if project_yaml.exists():
            try:
                pdata = yaml.safe_load(project_yaml.read_text()) or {}
                ptype = pdata.get("type", "")
                type_to_stack = {
                    "python-api": "FastAPI",
                    "automation": "Python",
                    "file-worker": "Python",
                    "node-api": "Node.js",
                    "file-api": "Node.js",
                    "saas-skeleton": "Next.js",
                    "chrome-extension": "Chrome MV3",
                    "mobile-app": "React Native",
                    "desktop-app": "Electron",
                    "static-site": "Next.js",
                    "wordpress": "WordPress",
                    "docusaurus": "Docusaurus",
                }
                if ptype in type_to_stack:
                    stack_parts.insert(0, type_to_stack[ptype])
            except Exception:
                pass

    return " + ".join(stack_parts) if stack_parts else "Unknown"


def _check_scaffold(path: Path) -> str:
    """Check scaffold compliance."""
    windsurfrules = path / ".windsurfrules"
    project_yaml = path / "project.yaml"

    if not windsurfrules.exists():
        return "❌ No scaffold"
    if windsurfrules.is_symlink():
        return "⚠️ Needs update (symlink)"
    if not project_yaml.exists():
        return "⚠️ No project.yaml"
    return "✅ Current"


def _auto_categorize(path: Path, status: str) -> str:
    """Auto-categorize project based on filesystem heuristics."""
    if status in ("production", "✅ Production"):
        return "production"
    has_compose = (path / "compose.yaml").exists()
    # Check for code in standard and non-standard locations
    has_code = (path / "src").exists() or (path / "app").exists()
    if not has_code:
        # Check for root .py files or requirements.txt as code indicators
        has_code = (path / "requirements.txt").exists() or (path / "pyproject.toml").exists()
    if not has_code:
        # Check for non-standard code dirs (api/, cli/, worker/, etc.)
        _skip = {
            "tests",
            "scripts",
            "docs",
            "db",
            "data",
            "logs",
            "config",
            "output",
            "node_modules",
            "venv",
            ".venv",
            "dist",
            "build",
            "migrations",
            "alembic",
            "cache",
            "chrome_profiles",
            "cookies",
        }
        try:
            for item in path.iterdir():
                if item.is_dir() and item.name not in _skip and not item.name.startswith("."):
                    if any(
                        f.suffix == ".py" for f in item.rglob("*.py") if "__pycache__" not in str(f)
                    ):
                        has_code = True
                        break
        except PermissionError:
            pass
    if has_compose and has_code:
        return "active"
    if (path / "README.md").exists() or (path / "docs").exists():
        return "planning"
    return "shell"


# ── Registry output ──────────────────────────────────────────────────────────


def save_registry(projects: list[Project]) -> Path:
    """Write aggregated data/projects.yaml."""
    registry_path = FABRIK_ROOT / "data" / "projects.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": 2,
        "last_scan": datetime.now().isoformat(),
        "total_projects": len(projects),
        "projects": {p.name: p.to_registry_dict() for p in sorted(projects, key=lambda x: x.name)},
    }

    registry_path.write_text(
        "# Auto-generated by sync_projects.py — do not hand-edit\n"
        + yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )
    return registry_path


# ── Deletion detection ───────────────────────────────────────────────────────


def detect_deletions(current_projects: list[Project]) -> list[str]:
    """Compare current scan against previous registry. Return names of deleted projects."""
    registry_path = FABRIK_ROOT / "data" / "projects.yaml"
    if not registry_path.exists():
        return []
    try:
        old_data = yaml.safe_load(registry_path.read_text()) or {}
        old_names = set(old_data.get("projects", {}).keys())
        current_names = {p.name for p in current_projects}
        return sorted(old_names - current_names)
    except Exception:
        return []


# ── BUSINESS_MODEL.md output ─────────────────────────────────────────────────


def generate_catalog_markdown(projects: list[Project], deleted: list[str]) -> str:
    """Generate markdown for project catalog."""
    production = [p for p in projects if p.category == "production"]
    active = [p for p in projects if p.category == "active"]
    planning = [p for p in projects if p.category == "planning"]
    shell = [p for p in projects if p.category == "shell"]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(projects)

    md = f"<!-- Last synced: {timestamp} -->\n"
    md += f"<!-- Total projects: {total} -->\n\n"

    for label, group in [
        ("Production Services", production),
        ("Active Development", active),
        ("Planning/Research", planning),
        ("Shell Projects", shell),
    ]:
        if not group:
            continue
        md += f"### {label} ({len(group)} projects)\n\n"
        md += "| Project | Purpose | Stack | Status | URL | Scaffold |\n"
        md += "|---------|---------|-------|--------|-----|----------|\n"
        for p in sorted(group, key=lambda x: x.name):
            url_display = p.url if p.url else "-"
            desc = p.description[:95] + "..." if len(p.description) > 98 else p.description
            md += f"| **{p.name}** | {desc} | {p.stack} | {p.status} | {url_display} | {p.scaffold_status} |\n"
        md += "\n"

    if deleted:
        md += f"### Recently Removed ({len(deleted)} projects)\n\n"
        md += "| Project | Note |\n|---------|------|\n"
        for name in deleted:
            md += f"| ~~{name}~~ | Folder deleted since last scan |\n"
        md += "\n"

    return md


def update_business_model(catalog_md: str) -> bool:
    """Update /opt/fabrik/docs/BUSINESS_MODEL.md AUTO-GENERATED block."""
    business_model_path = FABRIK_ROOT / "docs" / "BUSINESS_MODEL.md"

    if not business_model_path.exists():
        print(f"ERROR: {business_model_path} does not exist")
        return False

    content = business_model_path.read_text(encoding="utf-8")

    pattern = r"(<!-- AUTO-GENERATED:PROJECTS:START -->).*?(<!-- AUTO-GENERATED:PROJECTS:END -->)"
    replacement = f"\\1\n{catalog_md}\\2"

    if "AUTO-GENERATED:PROJECTS:START" not in content:
        content += "\n\n---\n\n## Project Portfolio\n\n"
        content += "<!-- AUTO-GENERATED:PROJECTS:START -->\n"
        content += catalog_md
        content += "<!-- AUTO-GENERATED:PROJECTS:END -->\n"
    else:
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    business_model_path.write_text(content, encoding="utf-8")
    return True


# ── Port conflict detection ──────────────────────────────────────────────────


def detect_port_conflicts(projects: list[Project]) -> dict[int, list[str]]:
    """Find projects claiming the same port. Returns {port: [project names]}."""
    port_map: dict[int, list[str]] = {}
    for p in projects:
        for port in p.ports:
            port_map.setdefault(port, []).append(p.name)
    return {port: names for port, names in port_map.items() if len(names) > 1}


def next_available_port(projects: list[Project], port_range: tuple[int, int] = (8000, 8099)) -> int:
    """Find the next unused port in the given range across all projects."""
    used: set[int] = set()
    for p in projects:
        used.update(p.ports)
    for port in range(port_range[0], port_range[1] + 1):
        if port not in used:
            return port
    return port_range[1] + 1  # Overflow — caller should handle


# ── PORTS.md auto-generation ─────────────────────────────────────────────────


def update_ports_md(projects: list[Project], conflicts: dict[int, list[str]]) -> bool:
    """Auto-generate the port allocation table in Fabrik's PORTS.md."""
    ports_path = FABRIK_ROOT / "PORTS.md"
    if not ports_path.exists():
        return False

    content = ports_path.read_text(encoding="utf-8")

    # Build the auto-generated block
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = f"<!-- Last synced: {timestamp} -->\n\n"

    # Conflict warnings
    if conflicts:
        md += "### ⚠️ Port Conflicts Detected\n\n"
        md += "| Port | Conflicting Projects |\n|------|---------------------|\n"
        for port, names in sorted(conflicts.items()):
            md += f"| **{port}** | {', '.join(names)} |\n"
        md += "\n"

    # Port allocations from project.yaml
    rows: list[tuple[int, str, str, str]] = []
    for p in projects:
        for port in p.ports:
            rows.append((port, p.name, p.type, p.path))
    if rows:
        md += "### Project Port Allocations (from project.yaml)\n\n"
        md += "| Port | Project | Type | Path |\n"
        md += "|------|---------|------|------|\n"
        for port, name, ptype, path in sorted(rows, key=lambda x: (x[0], x[1])):
            conflict_marker = " ⚠️" if any(name in names for names in conflicts.values()) else ""
            md += f"| {port}{conflict_marker} | **{name}** | {ptype} | {path} |\n"
        md += "\n"

    # Insert/replace AUTO-GENERATED block
    start_marker = "<!-- AUTO-GENERATED:PORTS:START -->"
    end_marker = "<!-- AUTO-GENERATED:PORTS:END -->"
    pattern = rf"({re.escape(start_marker)}).*?({re.escape(end_marker)})"

    if start_marker not in content:
        # Add block before the "Notes" section or at end
        insert_point = content.find("## Notes")
        if insert_point == -1:
            insert_point = len(content)
        block = f"\n{start_marker}\n{md}{end_marker}\n\n"
        content = content[:insert_point] + block + content[insert_point:]
    else:
        content = re.sub(pattern, f"\\1\n{md}\\2", content, flags=re.DOTALL)

    ports_path.write_text(content, encoding="utf-8")
    return True


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    """Scan projects, detect changes, update registry + BUSINESS_MODEL.md + PORTS.md."""
    print("📊 Scanning /opt/* projects...")

    projects = scan_projects()
    deleted = detect_deletions(projects)
    conflicts = detect_port_conflicts(projects)

    print(f"   Found {len(projects)} projects")
    if deleted:
        print(f"   🗑️  Removed since last scan: {', '.join(deleted)}")
    if conflicts:
        print("   ⚠️  Port conflicts:")
        for port, names in sorted(conflicts.items()):
            print(f"      Port {port}: {', '.join(names)}")

    # Save machine-readable registry
    registry_path = save_registry(projects)
    print(f"   📁 Registry: {registry_path}")

    # Update human-readable catalog
    catalog_md = generate_catalog_markdown(projects, deleted)
    if update_business_model(catalog_md):
        print("   📄 Updated docs/BUSINESS_MODEL.md")
    else:
        print("   ❌ Failed to update BUSINESS_MODEL.md")
        return 1

    # Update port allocations
    if update_ports_md(projects, conflicts):
        print("   📄 Updated PORTS.md")

    # Summary
    has_yaml = sum(1 for p in projects if (Path(p.path) / "project.yaml").exists())
    print(f"\n✅ Sync complete: {len(projects)} projects ({has_yaml} with project.yaml)")
    if conflicts:
        print(f"⚠️  {len(conflicts)} port conflict(s) — edit project.yaml to resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
