#!/usr/bin/env python3
"""
i18n Translation Validator — Automated quality checks via Kilo CLI.

Workflow:
  1. Coder AI (Claude/Cursor) generates the initial translation
  2. This script validates it via Kilo agents:
     Level 1: Structural checks (free, instant)
     Level 2: Back-translation via kilo ask agent (catches semantic errors)
     Level 3: Native-speaker critique via kilo ask agent (catches tone/grammar)

Usage:
  python scripts/validate_i18n.py                    # Level 1 only (free)
  python scripts/validate_i18n.py --validate tr      # Level 1 + 2 + 3 via Kilo
  python scripts/validate_i18n.py --review-csv tr    # Generate CSV for human review

Environment:
  KILO_I18N_MODEL    Model for validation (default: kilo/x-ai/grok-4.3)
  KILO_IDLE_TIMEOUT  Idle timeout in seconds (default: 120)
"""

import csv
import glob
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

I18N_DIR = Path(__file__).parent.parent / "dashboard" / "static" / "i18n"

# ── Kilo CLI integration ────────────────────────────────────────────────

KILO_BIN = None


def _find_kilo() -> str:
    global KILO_BIN
    if KILO_BIN:
        return KILO_BIN
    candidates = glob.glob("/home/*/.windsurf-server/extensions/kilocode.kilo-code-*/bin/kilo")
    if candidates:
        KILO_BIN = sorted(candidates)[-1]
        return KILO_BIN
    import shutil

    found = shutil.which("kilo")
    if found:
        KILO_BIN = found
        return KILO_BIN
    return ""


# Model selection per language — some models are better for specific languages
LANG_MODELS = {
    "tr": os.environ.get("KILO_I18N_MODEL", "kilo/x-ai/grok-4.3"),
    "es": os.environ.get("KILO_I18N_MODEL", "kilo/~google/gemini-pro-latest"),
    "pt-br": os.environ.get("KILO_I18N_MODEL", "kilo/~google/gemini-pro-latest"),
    "ja": os.environ.get("KILO_I18N_MODEL", "kilo/anthropic/claude-sonnet-4.6"),
    "id": os.environ.get("KILO_I18N_MODEL", "kilo/~google/gemini-pro-latest"),
}
DEFAULT_MODEL = os.environ.get("KILO_I18N_MODEL", "kilo/x-ai/grok-4.3")

KILO_IDLE_TIMEOUT = int(os.environ.get("KILO_IDLE_TIMEOUT", "120"))
KILO_HARD_TIMEOUT = int(os.environ.get("KILO_HARD_TIMEOUT", "300"))

LANG_NAMES = {
    "tr": "Turkish",
    "es": "Spanish",
    "pt-br": "Brazilian Portuguese",
    "ja": "Japanese",
    "id": "Indonesian",
}


def parse_kilo_jsonl(output: str) -> dict[str, Any]:
    """Parse Kilo JSONL output into structured result."""
    result_text = []
    session_id = ""
    input_tokens = 0
    output_tokens = 0
    cost = 0.0

    for line in output.strip().split("\n"):
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if "sessionID" in obj:
            session_id = obj["sessionID"]

        event_type = obj.get("type", "")

        if event_type == "error":
            error_data = obj.get("error", {})
            raise RuntimeError(f"Kilo API error: {error_data}")

        if event_type == "text":
            text = obj.get("text", "") or obj.get("part", {}).get("text", "")
            if text:
                result_text.append(text)

        elif event_type == "step_finish":
            tokens = obj.get("tokens") or obj.get("part", {}).get("tokens", {})
            input_tokens += tokens.get("input", 0)
            output_tokens += tokens.get("output", 0)
            cost += obj.get("cost", 0.0)

    return {
        "result": "".join(result_text),
        "session_id": session_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
    }


def run_kilo(
    prompt: str, model: str = None, session_id: str = None, file_path: str = None
) -> dict[str, Any]:
    """Run a prompt through kilo CLI with proper timeout monitoring."""
    kilo = _find_kilo()
    if not kilo:
        raise RuntimeError("kilo binary not found")

    cmd = [kilo, "run", "--format", "json", "--auto", "--agent", "ask", "--variant", "high"]

    if model:
        cmd.extend(["--model", model])
    if session_id:
        cmd.extend(["--session", session_id])
    if file_path:
        cmd.extend(["--file", file_path])

    cmd.append(prompt)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Monitor with idle + hard timeout
    stdout_parts = []
    stderr_parts = []  # noqa: F841
    last_output = time.time()
    start_time = time.time()

    stdout_q: queue.Queue = queue.Queue()

    def reader():
        try:
            while True:
                chunk = proc.stdout.read(8192)
                if not chunk:
                    break
                stdout_q.put(chunk)
        except Exception:
            pass
        stdout_q.put(None)

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    while True:
        try:
            chunk = stdout_q.get(timeout=1.0)
            if chunk is None:
                break
            stdout_parts.append(chunk.decode("utf-8", errors="replace"))
            last_output = time.time()
        except queue.Empty:
            pass

        if time.time() - last_output > KILO_IDLE_TIMEOUT:
            proc.kill()
            raise TimeoutError(f"Kilo idle timeout ({KILO_IDLE_TIMEOUT}s)")
        if time.time() - start_time > KILO_HARD_TIMEOUT:
            proc.kill()
            raise TimeoutError(f"Kilo hard timeout ({KILO_HARD_TIMEOUT}s)")

        if proc.poll() is not None:
            # Drain remaining
            while not stdout_q.empty():
                chunk = stdout_q.get_nowait()
                if chunk:
                    stdout_parts.append(chunk.decode("utf-8", errors="replace"))
            break

    proc.wait()
    return parse_kilo_jsonl("".join(stdout_parts))


def extract_json_from_text(text: str) -> Any:
    """Extract JSON from LLM response that may include markdown fences."""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts[1::2]:  # odd indices = inside fences
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    raise ValueError(f"Could not extract JSON from: {text[:200]}...")


# ── Helpers ──────────────────────────────────────────────────────────────


def flatten(d: dict, prefix: str = "") -> dict:
    items = {}
    for k, v in d.items():
        if k == "_meta":
            continue
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        else:
            items[key] = v
    return items


def load_lang(lang: str) -> dict:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def extract_placeholders(s: str) -> set:
    return set(re.findall(r"\{(\w+)\}", str(s)))


# ── Level 1: Structural validation ──────────────────────────────────────


def validate_structural(lang: str) -> list:
    issues = []
    en = flatten(load_lang("en"))
    tr = flatten(load_lang(lang))

    for k in en:
        if k not in tr:
            issues.append(f"MISSING_KEY: {k}")

    for k in tr:
        if k not in en:
            issues.append(f"EXTRA_KEY: {k}")

    for k in en:
        if k in tr:
            en_vars = extract_placeholders(en[k])
            tr_vars = extract_placeholders(tr[k])
            if en_vars != tr_vars:
                issues.append(f"PLACEHOLDER_MISMATCH: {k} EN={en_vars} {lang.upper()}={tr_vars}")

    for k, v in tr.items():
        if isinstance(v, str) and v.strip() == "":
            issues.append(f"EMPTY_VALUE: {k}")

    meta = load_lang(lang).get("_meta", {})
    actual = len(tr) / max(len(en), 1)
    declared = meta.get("completeness", 0)
    if abs(actual - declared) > 0.05:
        issues.append(f"COMPLETENESS_DRIFT: declared={declared} actual={actual:.2f}")

    return issues


# ── Level 2: Back-translation via Kilo ───────────────────────────────────


def back_translate(lang: str, sample_size: int = 30) -> list:
    """Back-translate target→EN via Kilo, compare with original EN."""
    kilo = _find_kilo()
    if not kilo:
        return ["SKIP: kilo binary not found"]

    en = flatten(load_lang("en"))
    tr = flatten(load_lang(lang))
    lang_name = LANG_NAMES.get(lang, lang)
    model = LANG_MODELS.get(lang, DEFAULT_MODEL)

    priority_prefixes = ["auth.", "queue.", "watchlists.", "common.", "failure.", "nav."]
    candidates = [k for k in en if any(k.startswith(p) for p in priority_prefixes)][:sample_size]
    strings_to_check = {k: tr[k] for k in candidates if k in tr and en[k] != tr[k]}

    if not strings_to_check:
        return []

    payload = json.dumps(strings_to_check, ensure_ascii=False)

    prompt = (
        f"Back-translate these {lang_name} SaaS UI strings to English. "
        f"These are button labels, form labels, confirmation dialogs, and status messages "
        f"from a SaaS product. "
        f"Return ONLY a valid JSON object with the same keys and English translations as values. "
        f"No markdown fences, no explanation. "
        f"Here are the strings: {payload}"
    )

    try:
        result = run_kilo(prompt, model=model)
        back = extract_json_from_text(result["result"])
        session = result.get("session_id", "")
        print(f"    [cost: ${result['cost']:.4f}, session: {session[:20]}...]")
    except Exception as e:
        return [f"BACK_TRANSLATE_ERROR: {e}"]

    issues = []
    for key in strings_to_check:
        original_en = en.get(key, "")
        back_en = back.get(key, "")
        if not back_en:
            continue

        def norm(s):
            s = re.sub(r"[^\w\s{}]", "", s.lower())
            return " ".join(s.split())

        orig_words = set(norm(original_en).split())
        back_words = set(norm(back_en).split())
        if not orig_words:
            continue
        overlap = len(orig_words & back_words) / len(orig_words)
        if overlap < 0.3:
            issues.append(
                f"SEMANTIC_DRIFT: {key}\n"
                f"  Original EN: {original_en}\n"
                f"  {lang.upper()}: {strings_to_check[key]}\n"
                f"  Back to EN: {back_en}\n"
                f"  Overlap: {overlap:.0%}"
            )

    return issues


# ── Level 3: Native-speaker critique via Kilo ────────────────────────────


def llm_critique(lang: str, session_id: str = None) -> tuple[list, str]:
    """Ask Kilo to critique translations as a native speaker. Returns (issues, session_id)."""
    kilo = _find_kilo()
    if not kilo:
        return ["SKIP: kilo binary not found"], ""

    en = flatten(load_lang("en"))
    tr = flatten(load_lang(lang))
    lang_name = LANG_NAMES.get(lang, lang)
    model = LANG_MODELS.get(lang, DEFAULT_MODEL)

    # Build review payload — all translated strings with English originals
    samples = {}
    for k in list(en.keys()):
        if k in tr and en[k] != tr[k]:
            samples[k] = {"en": en[k], lang: tr[k]}

    payload = json.dumps(samples, ensure_ascii=False)

    prompt = (
        f"You are a native {lang_name} speaker and a professional SaaS UI translator. "
        f"Review these English→{lang_name} UI translations for a SaaS product. "
        f"\n\n"
        f"Product context:\n"
        f"- This is a B2B/B2C SaaS product\n"
        f"- Tone: direct, technical, concise — like a senior engineer, not a marketing brochure\n"
        f'- Register: informal ("sen" not "siz" for Turkish, "tú" not "usted" for Spanish)\n'
        f"- Technical terms (API, JSON, transcript) stay English"
        f" if standard in {lang_name} tech culture\n"
        f"\n"
        f"For each issue found, report:\n"
        f"- key: the JSON key name\n"
        f"- type: WRONG_MEANING | WRONG_REGISTER | UNNATURAL"
        f" | TOO_LONG | WRONG_TECHNICAL_TERM | GRAMMAR\n"
        f"- problem: what is wrong\n"
        f"- fix: the corrected {lang_name} string\n"
        f"\n"
        f'Return ONLY a valid JSON object: {{"issues": [...]}}\n'
        f'Return {{"issues": []}} if everything is fine. No markdown, no explanation.\n\n'
        f"Translations: {payload}"
    )

    try:
        result = run_kilo(prompt, model=model, session_id=session_id)
        data = extract_json_from_text(result["result"])
        new_session = result.get("session_id", "")
        print(f"    [cost: ${result['cost']:.4f}, session: {new_session[:20]}...]")

        if isinstance(data, dict):
            data = data.get("issues", data.get("errors", []))
        if not isinstance(data, list):
            data = []
    except Exception as e:
        return [f"CRITIQUE_ERROR: {e}"], ""

    issues = []
    for item in data:
        if not isinstance(item, dict):
            continue
        issues.append(
            f"{item.get('type', 'UNKNOWN')}: {item.get('key', '?')}\n"
            f"  Problem: {item.get('problem', '?')}\n"
            f"  Fix: {item.get('fix', '?')}"
        )

    return issues, new_session


# ── Auto-fix from critique ───────────────────────────────────────────────


def apply_critique_fixes(lang: str, critique_issues: list):
    """Parse critique issues and apply suggested fixes to the JSON file."""
    # Extract fix suggestions from critique output
    fixes = {}
    for issue_text in critique_issues:
        lines = issue_text.split("\n")
        key = None
        fix = None
        for line in lines:
            # Parse "TYPE: key.name" from first line
            if ":" in line and not line.strip().startswith(("Problem:", "Fix:")):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key = parts[1].strip()
            if line.strip().startswith("Fix:"):
                fix = line.split("Fix:", 1)[1].strip()
        if key and fix and fix != "?":
            fixes[key] = fix

    if not fixes:
        return 0

    # Load and update JSON
    data = load_lang(lang)
    updated = 0
    for dotkey, new_value in fixes.items():
        keys = dotkey.split(".")
        obj = data
        for k in keys[:-1]:
            if isinstance(obj, dict) and k in obj:
                obj = obj[k]
            else:
                obj = None
                break
        if isinstance(obj, dict) and keys[-1] in obj:
            old = obj[keys[-1]]
            if old != new_value:
                obj[keys[-1]] = new_value
                print(f"    FIXED: {dotkey}")
                print(f"      Was: {old}")
                print(f"      Now: {new_value}")
                updated += 1

    if updated:
        path = I18N_DIR / f"{lang}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return updated


# ── Review CSV ───────────────────────────────────────────────────────────


def generate_review_csv(lang: str):
    en = flatten(load_lang("en"))
    tr = flatten(load_lang(lang))
    out_path = I18N_DIR / f"review_{lang}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "english", lang, "status", "notes"])
        for key in sorted(en.keys()):
            e = en[key]
            t = tr.get(key, "")
            status = "SAME" if e == t else "OK"
            w.writerow([key, e, t, status, ""])
    print(f"Review CSV: {out_path} ({len(en)} rows)")


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    args = sys.argv[1:]

    if "--review-csv" in args:
        lang = args[args.index("--review-csv") + 1]
        generate_review_csv(lang)
        return

    do_validate = "--validate" in args
    target_lang = None
    if do_validate:
        target_lang = args[args.index("--validate") + 1]

    langs = (
        [target_lang]
        if target_lang
        else [p.stem for p in I18N_DIR.glob("*.json") if p.stem != "en"]
    )
    if not langs:
        print("No translation files found")
        return

    all_pass = True
    for lang in langs:
        print(f"\n{'=' * 60}")
        print(f"  Validating: {lang}.json")
        print(f"  Model: {LANG_MODELS.get(lang, DEFAULT_MODEL)}")
        print(f"{'=' * 60}")

        # Level 1
        issues = validate_structural(lang)
        if issues:
            print(f"\n  Level 1 — Structural ({len(issues)} issues):")
            for i in issues:
                print(f"    {i}")
            all_pass = False
        else:
            print("\n  Level 1 — Structural: PASS")

        if not do_validate:
            continue

        # Level 2
        print("\n  Level 2 — Back-translation...")
        issues = back_translate(lang)
        skipped = any("SKIP:" in i for i in issues)
        real = [i for i in issues if "SKIP:" not in i]
        if skipped:
            print(f"    SKIPPED: {issues[0]}")
        elif real:
            print(f"    {len(real)} semantic drift(s):")
            for i in real:
                print(f"    {i}")
        else:
            print("    PASS — no semantic drift detected")

        # Level 3
        print("\n  Level 3 — Native-speaker critique...")
        issues, session_id = llm_critique(lang)
        skipped = any("SKIP:" in i for i in issues)
        real = [i for i in issues if "SKIP:" not in i and "ERROR" not in i]
        if skipped:
            print(f"    SKIPPED: {issues[0]}")
        elif real:
            print(f"    {len(real)} issue(s) found:")
            for i in real:
                print(f"    {i}")

            # Auto-apply fixes
            print("\n  Applying critique fixes...")
            fixed = apply_critique_fixes(lang, real)
            print(f"    Applied {fixed} fix(es)")
        else:
            err = [i for i in issues if "ERROR" in i]
            if err:
                print(f"    ERROR: {err[0]}")
            else:
                print("    PASS — no issues found")

    print(f"\n{'=' * 60}")
    if all_pass:
        print("  RESULT: ALL CHECKS PASSED")
    else:
        print("  RESULT: ISSUES FOUND")
    print(f"{'=' * 60}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
