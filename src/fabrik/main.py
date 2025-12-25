"""
Fabrik CLI entry point.

Usage:
    fabrik new <name> --template <template>
    fabrik plan <spec>
    fabrik apply <spec>
    fabrik status <spec>
    fabrik templates
"""

from fabrik.cli import main

if __name__ == "__main__":
    main()
