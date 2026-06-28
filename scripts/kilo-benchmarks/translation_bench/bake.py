#!/usr/bin/env python3
"""Translation Bake-Off v2 — corpus × model × language → chrF++ scores.

Improvements over fabrik-lib/mt-router bake-off v1 (2026-05-26):
  - Metric: chrF++ via sacrebleu (industry-standard) vs word-overlap (proxy).
  - Languages: 12 (added AR/DE/FR/HI/KO/ZH/IT) vs v1's 5 (TR/ES/PT/JA/ID).
  - Models: includes the operator's actual Kilo stack picks (GLM-5.2,
    Qwen3.7-Max, Gemini-3.1-Pro) so the same model answering chat ALSO has
    a measured translation score.
  - Corpus: 11 mixed-shape items (FLORES-200 prose + GUI strings + error
    messages + placeholder strings) vs v1's 10 GUI-only.
  - Cost-bounded: hard `budget_usd` ceiling; refuses to start if estimated
    cost exceeds budget.
  - Resumable: per-(model, sentence, lang) results cached to disk; re-runs
    pick up where they left off.
  - Idempotent: writes `translation_quality` JSON + `translation_avg_pct`
    to agents table when complete.

Usage:
    python bake.py --dry-run                      # estimate cost, no API calls
    python bake.py                                # run full bake
    python bake.py --langs tr,es --models grok-4.3,deepseek-v3.2  # subset
    python bake.py --resume                       # continue from cache

OpenRouter API key: env OPENROUTER_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

# Make `metric` importable when run from anywhere.
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from metric import chrf_plus_plus  # noqa: E402

CORPUS_PATH = SCRIPT_DIR / "corpus.json"
MODELS_PATH = SCRIPT_DIR / "models.yaml"
CACHE_DIR = SCRIPT_DIR / "cache"
RESULTS_PATH = SCRIPT_DIR / "results.json"

OR_URL = "https://openrouter.ai/api/v1/chat/completions"
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")


def _log(msg: str) -> None:
    print(f"[bake] {msg}")


def _today_utc_iso() -> str:
    return datetime.now(UTC).date().isoformat()


# ---------- I/O ----------


def load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def load_models() -> dict:
    return yaml.safe_load(MODELS_PATH.read_text(encoding="utf-8"))


def cache_key(model_id: str, sentence_id: str, lang: str) -> str:
    safe = model_id.replace("/", "__")
    return f"{safe}__{sentence_id}__{lang}.json"


def cache_load(model_id: str, sentence_id: str, lang: str) -> dict | None:
    p = CACHE_DIR / cache_key(model_id, sentence_id, lang)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def cache_save(model_id: str, sentence_id: str, lang: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = CACHE_DIR / cache_key(model_id, sentence_id, lang)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


# ---------- prompts ----------

LANG_NAMES = {
    "tr": "Turkish",
    "es": "Spanish",
    "pt": "Portuguese",
    "ja": "Japanese",
    "id": "Indonesian",
    "ar": "Arabic",
    "de": "German",
    "fr": "French",
    "hi": "Hindi",
    "ko": "Korean",
    "zh": "Simplified Chinese",
    "it": "Italian",
    "bn": "Bengali",
    "ru": "Russian",
    "ur": "Urdu",
    "pl": "Polish",
    "nl": "Dutch",
    "ro": "Romanian",
    "el": "Greek",
    "uk": "Ukrainian",
    "sv": "Swedish",
    "cs": "Czech",
    "hu": "Hungarian",
}


def build_prompt(source: str, target_lang: str, kind: str) -> tuple[str, str]:
    """Return (system, user) prompt pair. Translation-only — no commentary."""
    lang_name = LANG_NAMES[target_lang]
    system = (
        f"You are a professional translator. Translate the given text into {lang_name}. "
        "Output ONLY the translation — no explanations, no notes, no quotation marks. "
        "Preserve any placeholder tokens like {name}, {count}, {0} EXACTLY as-is "
        "(do not translate the placeholder names). Match the register and tone of "
        "the source."
    )
    if kind == "gui_short":
        system += " The source is a short UI label — keep the translation correspondingly short."
    elif kind == "gui_button":
        system += " The source is a button label — use imperative form when appropriate."
    elif kind == "error":
        system += " The source is an error message — be clear and direct."
    elif kind == "gui_placeholder":
        system += " The source contains {placeholder} tokens — keep them verbatim."
    user = source
    return system, user


# ---------- OpenRouter client ----------


def call_openrouter(
    model_id: str,
    system: str,
    user: str,
    max_tokens: int = 600,
    temperature: float = 0.0,
    timeout_s: int = 60,
) -> tuple[str, int, int]:
    """Returns (text, input_tokens, output_tokens)."""
    if not OR_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set in env")
    body = json.dumps(
        {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OR_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {OR_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mobasak/fabrik",
            "X-Title": "fabrik translation bake-off v2",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = json.loads(resp.read())
    text = payload["choices"][0]["message"]["content"].strip()
    usage = payload.get("usage") or {}
    return text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


# ---------- cost estimate ----------

# Rough OR prices in $/M tokens (for the dry-run estimate only; ACTUAL costs
# are read from agents.input_cost_per_m / output_cost_per_m in the DB if
# available, but for dry-run we want a quick proxy).
ROUGH_PRICES = {
    "deepseek/deepseek-v3.2": (0.23, 0.34),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "x-ai/grok-4.3": (1.25, 2.50),
    "mistralai/mistral-small-3.2-24b-instruct": (0.07, 0.20),
    "z-ai/glm-5.2": (0.95, 3.00),
    "qwen/qwen3.7-max": (1.25, 3.75),
    "google/gemini-3.1-pro-preview": (2.00, 12.00),
    "openai/gpt-oss-120b": (0.03, 0.15),
    "deepseek/deepseek-v4-flash": (0.09, 0.18),
}


def estimate_cost(
    corpus: dict, models_cfg: dict, langs: list[str] | None, models: list[str] | None
) -> tuple[float, int]:
    """Returns (estimated_usd, total_calls)."""
    if langs is None:
        langs = models_cfg["languages"]
    n_langs = len(langs)
    chosen_models = [m for m in models_cfg["models"] if (models is None or m["id"] in models)]
    n_sentences = len(corpus["sentences"])
    total_calls = n_sentences * n_langs * len(chosen_models)
    # Per-call token estimate: 100 in (prompt+source) + 100 out (translation avg)
    est = 0.0
    for m in chosen_models:
        rin, rout = ROUGH_PRICES.get(m["id"], (1.0, 3.0))
        per_model_calls = n_sentences * n_langs
        est += rin * per_model_calls * 100 / 1_000_000
        est += rout * per_model_calls * 100 / 1_000_000
    return est, total_calls


# ---------- bake loop ----------


def run_bake(
    corpus: dict,
    models_cfg: dict,
    langs: list[str] | None,
    models_filter: list[str] | None,
    resume: bool,
) -> dict:
    """Execute the bake. Returns a results dict suitable for writing
    to RESULTS_PATH + downstream DB integration."""
    if langs is None:
        langs = models_cfg["languages"]
    chosen_models = [
        m for m in models_cfg["models"] if (models_filter is None or m["id"] in models_filter)
    ]
    defaults = models_cfg.get("defaults") or {}

    # results[model_id][lang] = {scores: [...], n: int, avg: float}
    results: dict[str, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"per_sentence": [], "avg_chrf": None})
    )
    cost_usd = 0.0
    calls = 0
    cache_hits = 0
    failures = 0

    sentences = corpus["sentences"]
    total = len(chosen_models) * len(langs) * len(sentences)
    done = 0

    for model in chosen_models:
        mid = model["id"]
        rin, rout = ROUGH_PRICES.get(mid, (1.0, 3.0))
        for lang in langs:
            scores = []
            for s in sentences:
                done += 1
                if lang not in s["refs"]:
                    continue
                cached = cache_load(mid, s["id"], lang) if resume else None
                if cached and "translation" in cached:
                    hyp = cached["translation"]
                    cache_hits += 1
                else:
                    try:
                        system, user = build_prompt(s["source"], lang, s["kind"])
                        text, in_tok, out_tok = call_openrouter(
                            mid,
                            system,
                            user,
                            max_tokens=defaults.get("max_tokens", 600),
                            temperature=defaults.get("temperature", 0.0),
                            timeout_s=defaults.get("timeout_s", 60),
                        )
                        hyp = text
                        cost_usd += rin * in_tok / 1_000_000 + rout * out_tok / 1_000_000
                        calls += 1
                        cache_save(
                            mid,
                            s["id"],
                            lang,
                            {
                                "translation": hyp,
                                "input_tokens": in_tok,
                                "output_tokens": out_tok,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
                        _log(f"FAIL {mid:<40} {lang:<3} {s['id']:<10}: {e}")
                        failures += 1
                        continue

                ref = s["refs"][lang]
                score = chrf_plus_plus(hyp, [ref])
                scores.append({"id": s["id"], "kind": s["kind"], "hyp": hyp, "score": score})
                if done % 20 == 0:
                    _log(f"  progress: {done}/{total} (${cost_usd:.4f} so far)")

            results[mid][lang]["per_sentence"] = scores
            if scores:
                avg = sum(s["score"] for s in scores) / len(scores)
                results[mid][lang]["avg_chrf"] = round(avg, 2)
            _log(f"  {mid:<40} {lang:<3} avg_chrF={results[mid][lang]['avg_chrf']}")

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_version": corpus.get("_meta", {}).get("corpus_version"),
        "metric": "chrF++",
        "results": {mid: dict(by_lang) for mid, by_lang in results.items()},
        "stats": {
            "calls": calls,
            "cache_hits": cache_hits,
            "failures": failures,
            "approx_cost_usd": round(cost_usd, 4),
        },
    }


# ---------- DB integration ----------


def write_to_db(results: dict, db_path: Path) -> dict:
    """Write each model's per-lang chrF++ scores into agents.translation_quality
    JSON + the avg into translation_avg_pct."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    today = _today_utc_iso()
    counts = {"updated": 0, "skipped": 0}
    try:
        conn.execute("BEGIN")
        for mid, by_lang in results["results"].items():
            scores = {
                lang: by["avg_chrf"]
                for lang, by in by_lang.items()
                if by.get("avg_chrf") is not None
            }
            if not scores:
                counts["skipped"] += 1
                continue
            avg = sum(scores.values()) / len(scores)
            payload = {
                **scores,
                "avg": round(avg, 2),
                "source": f"fabrik translation bake-off v2 (chrF++) {today}",
                "_metric": "chrF++ via sacrebleu",
                "_corpus": results.get("corpus_version"),
            }
            cur = conn.execute(
                "UPDATE agents SET translation_quality = ?, translation_avg_pct = ?, "
                "is_translation_capable = 1, last_verified = ? WHERE id = ?",
                (json.dumps(payload, ensure_ascii=False), round(avg, 2), today, mid),
            )
            if cur.rowcount:
                counts["updated"] += 1
            else:
                counts["skipped"] += 1
        conn.commit()
    finally:
        conn.close()
    return counts


# ---------- CLI ----------


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="estimate cost only")
    p.add_argument("--langs", help="comma-separated subset (e.g. tr,es)")
    p.add_argument("--models", help="comma-separated subset of model id substrings")
    p.add_argument("--resume", action="store_true", help="reuse cached translations")
    p.add_argument(
        "--db",
        type=Path,
        default=SCRIPT_DIR.parent / "kilo_agents.db",
        help="agents DB to update on completion",
    )
    p.add_argument(
        "--no-db",
        action="store_true",
        help="don't write results into the DB (only emit results.json)",
    )
    args = p.parse_args()

    corpus = load_corpus()
    models_cfg = load_models()

    langs = args.langs.split(",") if args.langs else None
    models_filter = None
    if args.models:
        wanted_substrs = args.models.split(",")
        models_filter = [
            m["id"] for m in models_cfg["models"] if any(w in m["id"] for w in wanted_substrs)
        ]
        _log(f"models filtered to: {models_filter}")

    est_usd, total_calls = estimate_cost(corpus, models_cfg, langs, models_filter)
    _log(f"Estimated: {total_calls} API calls, ~${est_usd:.4f} USD")
    if est_usd > models_cfg.get("budget_usd", 10.0):
        _log(f"ABORT: estimate exceeds budget_usd={models_cfg['budget_usd']}")
        return 1
    if args.dry_run:
        return 0

    if not OR_KEY:
        _log("ERROR: OPENROUTER_API_KEY not in env. Set it to run.")
        return 1

    results = run_bake(corpus, models_cfg, langs, models_filter, args.resume)
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    _log(f"results written → {RESULTS_PATH}")
    _log(f"stats: {results['stats']}")

    if not args.no_db:
        counts = write_to_db(results, args.db)
        _log(f"DB updated: {counts}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
