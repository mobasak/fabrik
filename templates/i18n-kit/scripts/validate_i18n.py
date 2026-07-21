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

# Auto-detect i18n directory across all scaffold types.
# The validator reads the source-of-truth JSON from whichever location exists.
# For projects using adapters (chrome-extension, mobile-app), this still reads
# the canonical source JSON — the adapter output is generated FROM this.
_SCRIPT_ROOT = Path(__file__).parent.parent
_CANDIDATES = [
    _SCRIPT_ROOT / "static" / "i18n",                  # vanilla / desktop-app / static-site
    _SCRIPT_ROOT / "public" / "i18n",                   # Next.js (saas-skeleton)
    _SCRIPT_ROOT / "src" / "locales",                   # React Native (mobile-app) — i18next format
    _SCRIPT_ROOT / "i18n-source",                       # Docusaurus projects (source dir, NOT i18n/ which is output)
    _SCRIPT_ROOT / "dashboard" / "static" / "i18n",     # legacy (youtube/tojlo)
]
I18N_DIR = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])

# Chrome extension: after validating the source JSON, also validate the
# generated _locales/ files match (adapter may be stale).
_CHROME_LOCALES_DIR = _SCRIPT_ROOT / "extension" / "_locales"

# Product context — enriches Level 2 + Level 3 prompts with product name,
# description, tone, per-language register, tech terms to keep in English,
# and namespace descriptions.  Optional: if missing, prompts use generic defaults.
CONTEXT_PATH = I18N_DIR / "_context.json"
PRODUCT_CONTEXT = json.loads(CONTEXT_PATH.read_text(encoding="utf-8")) if CONTEXT_PATH.exists() else {}

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

KILO_IDLE_TIMEOUT = int(os.environ.get("KILO_IDLE_TIMEOUT", "300"))   # 5 min idle (safe — step_finish detection means this only fires if Kilo is truly stalled)
KILO_HARD_TIMEOUT = int(os.environ.get("KILO_HARD_TIMEOUT", "1200"))  # 20 min hard (738-key payloads take 3-8 min)

LANG_NAMES = {
    "tr": "Turkish",
    "es": "Spanish",
    "pt-br": "Brazilian Portuguese",
    "ja": "Japanese",
    "id": "Indonesian",
}


def parse_kilo_jsonl(output: str) -> dict[str, Any]:
    """Parse Kilo JSONL output into structured result.

    Validates that a ``step_finish`` event was received — the canonical
    completion signal in Kilo's JSONL stream.  Without it the LLM response
    is incomplete (truncated by timeout or crash).
    """
    result_text = []
    session_id = ""
    input_tokens = 0
    output_tokens = 0
    cost = 0.0
    has_step_finish = False

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
            has_step_finish = True
            tokens = obj.get("tokens") or obj.get("part", {}).get("tokens", {})
            input_tokens += tokens.get("input", 0)
            output_tokens += tokens.get("output", 0)
            cost += obj.get("cost", 0.0)

    if not has_step_finish:
        raise RuntimeError("Kilo run incomplete — no step_finish event received")

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

    # Monitor with step_finish detection (Kilo's JSONL completion signal).
    # Pattern from /opt/fabrik/scripts/kilo_code_review.py.
    stdout_parts = []
    last_output = time.time()
    start_time = time.time()
    has_step_finish = False

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
            decoded = chunk.decode("utf-8", errors="replace")
            stdout_parts.append(decoded)
            last_output = time.time()

            # Check if this chunk contains a step_finish event (Kilo is done)
            for line in decoded.strip().split("\n"):
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "step_finish":
                        has_step_finish = True
                except (json.JSONDecodeError, KeyError):
                    pass

        except queue.Empty:
            pass

        # If we got step_finish and process exited, we're done
        if has_step_finish and proc.poll() is not None:
            break

        # Idle timeout only if we haven't seen step_finish yet
        if not has_step_finish and time.time() - last_output > KILO_IDLE_TIMEOUT:
            proc.kill()
            raise TimeoutError(
                f"Kilo idle timeout ({KILO_IDLE_TIMEOUT}s) — no step_finish received"
            )
        if time.time() - start_time > KILO_HARD_TIMEOUT:
            proc.kill()
            raise TimeoutError(f"Kilo hard timeout ({KILO_HARD_TIMEOUT}s)")

        if proc.poll() is not None:
            # Process exited — drain remaining
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

    # Chrome extension: check _locales/ is in sync with source JSON
    if _CHROME_LOCALES_DIR.exists():
        chrome_lang_map = {"en": "en", "tr": "tr", "es": "es", "pt-br": "pt_BR", "ja": "ja", "id": "id"}
        chrome_code = chrome_lang_map.get(lang, lang)
        chrome_file = _CHROME_LOCALES_DIR / chrome_code / "messages.json"
        if chrome_file.exists():
            chrome_data = json.loads(chrome_file.read_text(encoding="utf-8"))
            chrome_keys = {k.replace("_", ".") for k in chrome_data}
            source_keys = set(tr.keys())
            stale = source_keys - chrome_keys
            if stale:
                issues.append(
                    f"CHROME_LOCALES_STALE: {len(stale)} key(s) in {lang}.json "
                    f"missing from _locales/{chrome_code}/messages.json — "
                    f"run: python adapters/chrome_messages.py"
                )
        elif lang == "en":
            issues.append(
                f"CHROME_LOCALES_MISSING: _locales/{chrome_code}/messages.json not found — "
                f"run: python adapters/chrome_messages.py"
            )

    # React Native: check src/locales/ is in sync with source JSON
    rn_locales = _SCRIPT_ROOT / "src" / "locales"
    if rn_locales.exists() and rn_locales != I18N_DIR:
        rn_file = rn_locales / f"{lang}.json"
        if rn_file.exists():
            rn_data = flatten(json.loads(rn_file.read_text(encoding="utf-8")))
            if set(rn_data.keys()) != set(tr.keys()):
                issues.append(
                    f"RN_LOCALES_STALE: src/locales/{lang}.json out of sync — "
                    f"run: python adapters/sync_rn_locales.py"
                )

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

    product = PRODUCT_CONTEXT.get("product_name", "a SaaS product")
    desc = PRODUCT_CONTEXT.get("product_description", "")
    product_ctx = f"{product} ({desc})" if desc else product

    prompt = (
        f"Back-translate these {lang_name} UI strings to English. "
        f"These are from {product_ctx}. "
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

    product = PRODUCT_CONTEXT.get("product_name", "a SaaS product")
    desc = PRODUCT_CONTEXT.get("product_description", "")
    tone = PRODUCT_CONTEXT.get("tone", "direct, technical, concise")
    register = PRODUCT_CONTEXT.get("register", {}).get(lang, "informal")
    tech_terms = ", ".join(PRODUCT_CONTEXT.get("tech_terms_keep_english", ["API", "JSON"]))
    ns_context = PRODUCT_CONTEXT.get("namespace_context", {})

    # Build namespace hints for the keys being reviewed
    ns_hints = set()
    for key in samples:
        ns = key.split(".")[0]
        if ns in ns_context:
            ns_hints.add(f"- {ns}.*: {ns_context[ns]}")
    ns_block = "\n".join(sorted(ns_hints)) if ns_hints else "(no namespace context provided)"

    prompt = (
        f"You are a native {lang_name} speaker and a professional SaaS UI translator. "
        f"Review these English→{lang_name} UI translations for {product}."
        f"\n\n"
        f"Product: {desc}\n"
        f"Tone: {tone}\n"
        f"Register for {lang_name}: {register}\n"
        f"Keep these terms in English: {tech_terms}\n"
        f"\n"
        f"Where these strings appear in the UI:\n{ns_block}\n"
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
        else [p.stem for p in I18N_DIR.glob("*.json") if p.stem != "en" and not p.stem.endswith(".example") and not p.stem.startswith("_")]
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
