#!/usr/bin/env python3
"""Deploy .doc-policy.md to all /opt/* projects (excluding _* prefixes)."""

from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
DOC_POLICY_TEMPLATE = FABRIK_ROOT / "templates" / "docs" / ".doc-policy.md"


def main():
    """Deploy doc policy to all active /opt projects."""
    if not DOC_POLICY_TEMPLATE.exists():
        print(f"❌ Template not found: {DOC_POLICY_TEMPLATE}")
        return 1

    template_content = DOC_POLICY_TEMPLATE.read_text()
    opt_dir = Path("/opt")
    deployed = []
    skipped = []

    for project_dir in sorted(opt_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        project_name = project_dir.name

        # Skip _* prefixed projects (inactive/templates)
        if project_name.startswith("_"):
            skipped.append(f"{project_name} (inactive)")
            continue

        # Skip if docs/ doesn't exist (not a scaffolded project)
        docs_dir = project_dir / "docs"
        if not docs_dir.exists():
            skipped.append(f"{project_name} (no docs/)")
            continue

        # Deploy policy file
        policy_path = docs_dir / ".doc-policy.md"
        if policy_path.exists():
            skipped.append(f"{project_name} (already exists)")
            continue

        policy_path.write_text(template_content)
        deployed.append(project_name)
        print(f"✅ {project_name}")

    print("\n📊 Summary:")
    print(f"  Deployed: {len(deployed)}")
    print(f"  Skipped: {len(skipped)}")

    if deployed:
        print(f"\n✅ Deployed to: {', '.join(deployed)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
