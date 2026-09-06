#!/usr/bin/env python3
# AFTER-EDIT: none
"""Gate: verify every Zed extension that settings.json depends on is installed.

Reads Zed's own source of truth (``extensions/index.json``), derives the REQUIRED
set from ``settings.json`` (language servers + themes) so the gate stays in sync
with the config, and exits non-zero if anything is missing.

Usage:
    python check_zed_extensions.py [--json] [--settings PATH] [--extensions-dir PATH]

Exit code 0 = all required extensions installed; 1 = something missing/not found.

Mappings below are explicit on purpose (a language-server NAME is not always its
extension ID). Extend SERVER_TO_EXTENSION / THEME_TO_EXTENSION as you add tooling.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# --- what needs an extension vs. what Zed bundles -------------------------------
# value = Zed extension id required for that language server; None = built-in.
SERVER_TO_EXTENSION: dict[str, str | None] = {
    "ruff": "ruff",
    "basedpyright": "basedpyright",
    "pyright": None,  # bundled with Zed's Python support
}
# themes provided by an extension; anything not listed is assumed Zed built-in.
THEME_TO_EXTENSION: dict[str, str] = {
    "VSCode Modern Dark": "vscode-modern",
    "VSCode Modern Light": "vscode-modern",
    "VSCode Modern": "vscode-modern",
}


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments (string-aware) + trailing commas."""
    out: list[str] = []
    i, n = 0, len(text)
    instr = esc = False
    while i < n:
        c = text[i]
        if instr:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
            i += 1
            continue
        if c == '"':
            instr = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    import re

    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _win_user_dirs() -> list[Path]:
    return sorted(Path("/mnt/c/Users").glob("*")) if Path("/mnt/c/Users").is_dir() else []


def _first_readable(candidates: list[Path]) -> Path | None:
    for p in candidates:
        try:
            if p.is_file():
                return p
        except OSError:  # unreadable Windows profiles (Administrator, etc.)
            continue
    return None


def find_settings(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    candidates: list[Path] = [Path.home() / ".config/zed/settings.json"]
    for u in _win_user_dirs():
        candidates.append(u / "AppData/Roaming/Zed/settings.json")
    return _first_readable(candidates)


def find_extensions_index(explicit: str | None) -> Path | None:
    if explicit:
        d = Path(explicit)
        return d / "index.json" if d.is_dir() else d
    candidates: list[Path] = [Path.home() / ".local/share/zed/extensions/index.json"]
    for u in _win_user_dirs():
        candidates.append(u / "AppData/Local/Zed/extensions/index.json")
    return _first_readable(candidates)


def installed_ids(index_path: Path) -> set[str]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    ids = set(data.get("extensions", {}).keys())
    # belt-and-suspenders: also trust folders under installed/
    inst = index_path.parent / "installed"
    if inst.is_dir():
        ids |= {p.name for p in inst.iterdir() if p.is_dir()}
    return ids


def required_from_settings(settings_path: Path) -> tuple[dict[str, str], list[str]]:
    """Return {extension_id: reason} required, plus warnings for unknown servers."""
    cfg = json.loads(strip_jsonc(settings_path.read_text(encoding="utf-8")))
    required: dict[str, str] = {}
    warnings: list[str] = []

    for lang, spec in (cfg.get("languages") or {}).items():
        for server in (spec or {}).get("language_servers", []):
            server = server.lstrip("!")  # Zed uses "!name" to disable
            if not server:
                continue
            if server in SERVER_TO_EXTENSION:
                ext = SERVER_TO_EXTENSION[server]
                if ext:
                    required.setdefault(ext, f'{lang} language server "{server}"')
            else:
                warnings.append(
                    f'unknown language server "{server}" ({lang}) — add it to '
                    f"SERVER_TO_EXTENSION to gate it"
                )

    theme = cfg.get("theme") or {}
    for slot in ("dark", "light"):
        name = theme.get(slot)
        if isinstance(name, str) and name in THEME_TO_EXTENSION:
            required.setdefault(THEME_TO_EXTENSION[name], f'theme "{name}"')
    return required, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify required Zed extensions are installed.")
    ap.add_argument("--settings", help="path to Zed settings.json")
    ap.add_argument("--extensions-dir", help="path to Zed extensions dir (or its index.json)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--check", action="store_true", help="alias for default read-only run")
    args = ap.parse_args()

    settings = find_settings(args.settings or os.environ.get("ZED_SETTINGS"))
    index = find_extensions_index(args.extensions_dir or os.environ.get("ZED_EXTENSIONS_DIR"))

    problems: list[str] = []
    if not settings:
        problems.append("settings.json not found (pass --settings)")
    if not index:
        problems.append("extensions/index.json not found (pass --extensions-dir)")
    if problems:
        payload = {"status": "error", "errors": problems}
        print(json.dumps(payload, indent=2) if args.json else "ERROR: " + "; ".join(problems))
        return 1

    installed = installed_ids(index)
    required, warnings = required_from_settings(settings)
    missing = {ext: why for ext, why in required.items() if ext not in installed}

    if args.json:
        print(
            json.dumps(
                {
                    "status": "success" if not missing else "failure",
                    "settings": str(settings),
                    "extensions_index": str(index),
                    "installed": sorted(installed),
                    "required": required,
                    "missing": missing,
                    "warnings": warnings,
                },
                indent=2,
            )
        )
        return 0 if not missing else 1

    print(f"settings : {settings}")
    print(f"index    : {index}")
    print(f"installed: {', '.join(sorted(installed)) or '(none)'}\n")
    if not required:
        print("No extension-backed tooling referenced in settings.json — nothing to gate.")
    for ext, why in sorted(required.items()):
        mark = "OK  " if ext in installed else "MISS"
        print(f"  [{mark}] {ext:<16} — {why}")
    for w in warnings:
        print(f"  [WARN] {w}")
    if missing:
        print(
            f"\nFAIL: {len(missing)} extension(s) missing — install via zed: extensions "
            f"({', '.join(sorted(missing))})."
        )
        return 1
    print("\nOK: all required Zed extensions are installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
