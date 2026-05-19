#!/usr/bin/env python3
"""
Sync i18n-kit JSON → React Native i18next locale files.

i18next uses the same nested JSON format as i18n-kit, so this is mostly a
copy + validate operation. The value-add is:
  1. Copies to the i18next-expected path (src/locales/<lang>.json)
  2. Generates the i18next config snippet if missing
  3. Runs structural validation (same as validate_i18n.py Level 1)

Usage:
  python adapters/sync_rn_locales.py                  # sync all languages
  python adapters/sync_rn_locales.py --lang tr        # sync one language
  python adapters/sync_rn_locales.py --init           # generate i18next config + sync

Reads from:  static/i18n/<lang>.json  (i18n-kit format)
Writes to:   src/locales/<lang>.json  (React Native i18next)
"""

import json
import logging
import re
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

I18N_DIR = PROJECT_ROOT / "static" / "i18n"
RN_LOCALES_DIR = PROJECT_ROOT / "src" / "locales"

I18NEXT_CONFIG = """\
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import * as Localization from 'expo-localization';

// Import locale files
{imports}

const resources = {{
{resources}
}};

const supported = [{supported}];
const deviceLang = Localization.locale.split('-')[0].toLowerCase();
const lang = supported.includes(deviceLang) ? deviceLang : 'en';

i18n
  .use(initReactI18next)
  .init({{
    resources,
    lng: lang,
    fallbackLng: 'en',
    interpolation: {{ escapeValue: false }},
    compatibilityJSON: 'v4',
  }});

export default i18n;
"""


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


def validate_structural(lang: str) -> list[str]:
    """Quick structural check (same as validate_i18n.py Level 1)."""
    en_path = I18N_DIR / "en.json"
    lang_path = I18N_DIR / f"{lang}.json"
    if not en_path.exists() or not lang_path.exists():
        return [f"MISSING_FILE: {lang_path}"]

    en = flatten(json.loads(en_path.read_text(encoding="utf-8")))
    tr = flatten(json.loads(lang_path.read_text(encoding="utf-8")))
    issues = []
    for k in en:
        if k not in tr:
            issues.append(f"MISSING_KEY: {k}")
    for k in tr:
        if k not in en:
            issues.append(f"EXTRA_KEY: {k}")
    for k in en:
        if k in tr:
            en_vars = set(re.findall(r"\{(\w+)\}", str(en[k])))
            tr_vars = set(re.findall(r"\{(\w+)\}", str(tr[k])))
            if en_vars != tr_vars:
                issues.append(f"PLACEHOLDER_MISMATCH: {k}")
    return issues


def sync_lang(lang: str) -> bool:
    """Copy one language file to src/locales/. Returns True on success."""
    src = I18N_DIR / f"{lang}.json"
    if not src.exists():
        logger.info("  SKIP: %s not found", src)
        return False

    # Validate first
    issues = validate_structural(lang) if lang != "en" else []
    if issues:
        logger.warning("  WARN: %s has %d structural issue(s):", lang, len(issues))
        for i in issues[:5]:
            logger.warning("    %s", i)
        if len(issues) > 5:
            logger.warning("    ... and %d more", len(issues) - 5)

    RN_LOCALES_DIR.mkdir(parents=True, exist_ok=True)
    dest = RN_LOCALES_DIR / f"{lang}.json"
    shutil.copy2(src, dest)
    logger.info("  %s → %s", lang, dest.relative_to(PROJECT_ROOT))
    return True


def generate_config(langs: list[str]) -> None:
    """Generate src/locales/i18n.ts config file."""
    imports = "\n".join(f"import {l.replace('-', '_')} from './{l}.json';" for l in langs)
    resources = "\n".join(f"  {l.replace('-', '_')}: {{ translation: {l.replace('-', '_')} }}," for l in langs)
    supported = ", ".join(f"'{l}'" for l in langs)

    config = I18NEXT_CONFIG.format(imports=imports, resources=resources, supported=supported)
    out = RN_LOCALES_DIR / "i18n.ts"
    out.write_text(config, encoding="utf-8")
    logger.info("  Config → %s", out.relative_to(PROJECT_ROOT))


def main() -> None:
    args = sys.argv[1:]
    do_init = "--init" in args

    if "--lang" in args:
        langs = []
        for i, a in enumerate(args):
            if a == "--lang" and i + 1 < len(args):
                langs.append(args[i + 1])
    else:
        langs = sorted(
            p.stem for p in I18N_DIR.glob("*.json") if not p.stem.endswith(".example")
        )

    # Ensure 'en' is first
    if "en" in langs:
        langs.remove("en")
        langs.insert(0, "en")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Syncing %d language(s) to src/locales/:", len(langs))
    synced = []
    for lang in langs:
        if sync_lang(lang):
            synced.append(lang)

    if do_init and synced:
        logger.info("\nGenerating i18next config:")
        generate_config(synced)

    logger.info("\nDone. %d language(s) synced.", len(synced))


if __name__ == "__main__":
    main()
