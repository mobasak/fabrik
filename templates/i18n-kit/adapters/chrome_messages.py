#!/usr/bin/env python3
"""
Convert i18n-kit en.json → Chrome Extension _locales/<lang>/messages.json.

Chrome's i18n API uses a flat format:
  { "nav_home": { "message": "Home", "description": "Navigation: Home link" } }

This script reads the nested i18n-kit JSON and generates Chrome-compatible files.

Usage:
  python adapters/chrome_messages.py                          # all languages
  python adapters/chrome_messages.py --lang en --lang tr      # specific languages
  python adapters/chrome_messages.py --dry-run                # preview without writing

Reads from:  static/i18n/<lang>.json  (i18n-kit format)
Writes to:   extension/_locales/<lang>/messages.json  (Chrome format)
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Auto-detect project root (look for extension/ or _locales/)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Configurable paths — override these if your project structure differs
I18N_DIR = PROJECT_ROOT / "static" / "i18n"
LOCALES_DIR = PROJECT_ROOT / "extension" / "_locales"

# Chrome uses BCP-47 with underscores, not hyphens
LANG_MAP = {
    "en": "en",
    "tr": "tr",
    "es": "es",
    "pt-br": "pt_BR",
    "ja": "ja",
    "id": "id",
}


def flatten(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested JSON to dot-path keys."""
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


def to_chrome_key(dot_key: str) -> str:
    """Convert 'nav.home' → 'nav_home' (Chrome doesn't allow dots in keys)."""
    return dot_key.replace(".", "_")


def convert(lang: str, dry_run: bool = False) -> int:
    """Convert one language. Returns number of keys written."""
    src = I18N_DIR / f"{lang}.json"
    if not src.exists():
        logger.info("  SKIP: %s not found", src)
        return 0

    data = json.loads(src.read_text(encoding="utf-8"))
    flat = flatten(data)

    chrome_lang = LANG_MAP.get(lang, lang)
    messages: dict[str, dict[str, str]] = {}

    for dot_key, value in sorted(flat.items()):
        chrome_key = to_chrome_key(dot_key)
        messages[chrome_key] = {
            "message": value,
            "description": dot_key,  # original dot-path as description for translators
        }

    if dry_run:
        logger.info("  %s → _locales/%s/messages.json (%d keys)", lang, chrome_lang, len(messages))
        return len(messages)

    out_dir = LOCALES_DIR / chrome_lang
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "messages.json"
    out_file.write_text(json.dumps(messages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("  %s → %s (%d keys)", lang, out_file.relative_to(PROJECT_ROOT), len(messages))
    return len(messages)


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args

    if "--lang" in args:
        langs = []
        for i, a in enumerate(args):
            if a == "--lang" and i + 1 < len(args):
                langs.append(args[i + 1])
    else:
        langs = [p.stem for p in I18N_DIR.glob("*.json") if not p.stem.endswith(".example")]

    if not I18N_DIR.exists():
        # Try project-level paths
        for candidate in [
            Path.cwd() / "static" / "i18n",
            Path.cwd() / "public" / "i18n",
        ]:
            if candidate.exists():
                globals()["I18N_DIR"] = candidate
                break

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Converting %d language(s) to Chrome _locales/ format:", len(langs))
    total = 0
    for lang in langs:
        total += convert(lang, dry_run=dry_run)
    logger.info("Done. %d total keys.", total)

    if dry_run:
        logger.info("(dry-run — no files written)")


if __name__ == "__main__":
    main()
