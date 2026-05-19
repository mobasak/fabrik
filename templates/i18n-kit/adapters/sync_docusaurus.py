#!/usr/bin/env python3
"""
Sync i18n-kit custom strings → Docusaurus i18n/<lang>/code.json.

Docusaurus has built-in i18n for docs/blog/React components via its Git-based
folder structure (per rule 42-docusaurus). This adapter handles ONLY custom
UI strings (navbar, footer, homepage, custom React components) that Docusaurus
stores in i18n/<lang>/code.json.

Docusaurus code.json format is flat with message + description:
  {
    "theme.navbar.title": { "message": "My Site", "description": "Navbar title" },
    "homepage.tagline": { "message": "Build fast", "description": "Homepage tagline" }
  }

This script converts from i18n-kit's nested format, using dot-paths as keys.
Only keys under designated top-level sections are synced (not the full JSON).

Usage:
  python adapters/sync_docusaurus.py                        # sync all languages
  python adapters/sync_docusaurus.py --lang tr              # sync one language
  python adapters/sync_docusaurus.py --sections nav,common  # custom section filter
  python adapters/sync_docusaurus.py --dry-run              # preview

Reads from:  static/i18n/<lang>.json or i18n/<lang>.json  (i18n-kit format)
Writes to:   i18n/<lang>/code.json  (Docusaurus format, merged with existing)
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Sections from en.json to sync. Docusaurus-specific sections only.
# Docs and blog content use Docusaurus' native markdown i18n, not this.
DEFAULT_SECTIONS = ["nav", "common", "footer", "homepage", "theme", "error"]

# Docusaurus i18n output directory
DOCUSAURUS_I18N_DIR = PROJECT_ROOT / "i18n"

# Source JSON — same auto-detection as validate_i18n.py
_CANDIDATES = [
    PROJECT_ROOT / "static" / "i18n",
    PROJECT_ROOT / "i18n-source",  # dedicated source dir to avoid collision with Docusaurus i18n/
    PROJECT_ROOT / "public" / "i18n",
]
I18N_SOURCE_DIR = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])


def flatten(d: dict, prefix: str = "") -> dict[str, str]:
    items: dict[str, str] = {}
    for k, v in d.items():
        if k == "_meta":
            continue
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, str):
            items[key] = v
    return items


def convert(lang: str, sections: list[str], dry_run: bool = False) -> int:
    """Convert one language. Returns number of keys written."""
    src = I18N_SOURCE_DIR / f"{lang}.json"
    if not src.exists():
        logger.info("  SKIP: %s not found", src)
        return 0

    data = json.loads(src.read_text(encoding="utf-8"))
    flat = flatten(data)

    # Filter to designated sections only
    filtered = {k: v for k, v in flat.items() if k.split(".")[0] in sections}

    if not filtered:
        logger.info("  SKIP: %s has no keys in sections %s", lang, sections)
        return 0

    # Build Docusaurus code.json format
    code_json: dict[str, dict[str, str]] = {}
    for key, value in sorted(filtered.items()):
        code_json[key] = {
            "message": value,
            "description": key,
        }

    if dry_run:
        logger.info("  %s → i18n/%s/code.json (%d keys)", lang, lang, len(code_json))
        return len(code_json)

    # Merge with existing code.json (Docusaurus may have extracted its own keys)
    out_dir = DOCUSAURUS_I18N_DIR / lang
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "code.json"

    existing: dict = {}
    if out_file.exists():
        existing = json.loads(out_file.read_text(encoding="utf-8"))

    # Our keys overwrite, but we don't delete Docusaurus-extracted keys
    existing.update(code_json)

    out_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("  %s → %s (%d synced, %d total)", lang, out_file.relative_to(PROJECT_ROOT), len(code_json), len(existing))
    return len(code_json)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = sys.argv[1:]
    dry_run = "--dry-run" in args

    sections = DEFAULT_SECTIONS
    if "--sections" in args:
        idx = args.index("--sections")
        sections = args[idx + 1].split(",")

    if "--lang" in args:
        langs = []
        for i, a in enumerate(args):
            if a == "--lang" and i + 1 < len(args):
                langs.append(args[i + 1])
    else:
        langs = sorted(
            p.stem for p in I18N_SOURCE_DIR.glob("*.json") if not p.stem.endswith(".example")
        )

    logger.info("Syncing %d language(s) to Docusaurus i18n/*/code.json:", len(langs))
    logger.info("  Sections: %s", sections)
    total = 0
    for lang in langs:
        total += convert(lang, sections, dry_run=dry_run)
    logger.info("Done. %d total keys.", total)

    if dry_run:
        logger.info("(dry-run — no files written)")


if __name__ == "__main__":
    main()
