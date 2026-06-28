# Translation Bake-Off v2

Cost-bounded, resumable translation quality measurement against human references
using **chrF++** (sacrebleu, WMT-standard since 2020), feeding the
`translation_quality` JSON and `translation_avg_pct` columns on `agents`.

## What v2 changes vs the fabrik-lib v1 bake-off

| Axis | v1 (2026-05-26) | v2 (this) |
|---|---|---|
| Metric | word-overlap (EU) / char-overlap (CJK) | **chrF++** (single metric across all scripts) |
| Languages | 5 (TR/ES/PT/JA/ID) | **23** (v2 +AR/DE/FR/HI/KO/ZH/IT; v2.2 +BN/RU/UR top-10 + PL/NL/RO/EL/UK/SV/CS/HU common European) |
| Models | 7 (mt-router TIER3 + DeepL + Azure) | **9** (adds operator's Kilo stack: GLM-5.2, Qwen3.7-Max, Gemini-3.1-Pro, gpt-oss-120b, deepseek-v4-flash) |
| Corpus | 10 strings, GUI-only | **11+** strings, mixed (FLORES-200 prose + GUI + errors + placeholders) |
| Resumable | no | **yes** (per-call cache; restart from any failure point) |
| Cost-bounded | no | **yes** (refuses to start above `budget_usd` ceiling) |
| Idempotent | manual | **yes** (writes to DB on completion; safe to re-run) |

## chrF++ vs the v1 word-overlap metric

BLEU and naive word-overlap penalize perfectly correct translations whenever
morphology, word order, or tokenization differs from the reference. chrF++
operates on character n-grams with a word n-gram weight (`char_order=6`,
`word_order=2`, `beta=2` — the WMT 2020+ default), giving partial credit
for morphologically-close output AND tokenizing CJK uniformly with European
languages. This is why v1 and v2 scores aren't directly comparable: same
translation, different metric.

## Files

```
translation_bench/
├── README.md            ← you are here
├── corpus.json          ← source strings + human references per language
├── models.yaml          ← which models to test (9 by default), budget cap
├── metric.py            ← chrF++ via sacrebleu
├── bake.py              ← main harness (OpenRouter chat-completions API)
├── cache/               ← per-(model, sentence, lang) result cache
└── results.json         ← latest bake summary
```

## Run it

```bash
# Estimate cost without API calls
.venv/bin/python scripts/kilo-benchmarks/translation_bench/bake.py --dry-run

# Run full bake (all 9 models × 12 langs × 11 sentences ≈ $0.30)
OPENROUTER_API_KEY=... \
  .venv/bin/python scripts/kilo-benchmarks/translation_bench/bake.py

# Subset (cheap models on 2 langs)
OPENROUTER_API_KEY=... \
  .venv/bin/python scripts/kilo-benchmarks/translation_bench/bake.py \
    --langs tr,es \
    --models deepseek-v3.2,gpt-oss-120b,grok-4.3 \
    --resume

# Resume an interrupted run (skips cached calls)
OPENROUTER_API_KEY=... \
  .venv/bin/python scripts/kilo-benchmarks/translation_bench/bake.py --resume

# Don't write to DB (just emit results.json)
OPENROUTER_API_KEY=... \
  .venv/bin/python scripts/kilo-benchmarks/translation_bench/bake.py --no-db
```

## DB integration

On completion, `bake.py` writes one row per tested model:

- `agents.translation_quality` — JSON with per-language chrF++ + `avg` + `source` + `_metric` + `_corpus`
- `agents.translation_avg_pct` — the avg as a scalar (sortable in browser)
- `agents.is_translation_capable = 1`
- `agents.last_verified = today_utc`

The browser's existing "Trans" column reflects the latest avg. Hover any
Trans cell to see the per-language breakdown.

## Reference corpus

Currently embeds 11 source strings with human references for 12 languages:

- **15 FLORES-200 dev-split sentences** (prose, Wikipedia-style, CC-BY-SA)
- **5 GUI-style strings** (short labels, button text, placeholder substitution)
- **5 error messages** (system-flavored prose)

To expand: edit `corpus.json` directly. Reference quality matters more than
sentence count — never add a sentence without a vetted reference for every
target language, because chrF++ scores against the reference; a poor reference
penalizes every model uniformly.

## Sweet-spot models the operator tracks

`models.yaml::sweet_spots` lists the routes the operator considers
production-grade for i18n translation routing. Currently:

- **`x-ai/grok-4.3`** — confirmed v2 leader (chrF++ avg 86.6 on 5 langs).
  Reachable via OpenRouter, in the bake-off matrix.
- **`qwen-mt-pro`** — Alibaba DashScope dedicated MT model, higher tier than
  `qwen-mt-turbo`. **NOT yet testable via this harness** — DashScope's API
  surface differs from OpenRouter's chat-completions shape, and the
  harness currently only supports OpenRouter. To enable: extend `bake.py`
  with a DashScope provider router that calls the
  `https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation`
  endpoint with a DashScope API key from `DASHSCOPE_API_KEY` env. The
  request/response shape is documented at
  `https://help.aliyun.com/zh/dashscope/developer-reference/api-details`.
  Plumbing this in is ~50 LOC; the metric and corpus already work with
  any provider that returns a translation string.

## Re-bake cadence

Run on:

1. **Major model release** that hits OpenRouter (any new T3 from OpenAI, Google,
   Anthropic-via-OpenRouter, DeepSeek, Qwen). New rows get scored without
   re-running cached models.
2. **Monthly** if any model in `models.yaml` is marked `preview` — preview
   models can change behavior between revisions.
3. **Any mt-router change** — if the bake-off informs TIER3_MODEL_MAP, re-run
   before merging the change.

Each re-bake costs $0.30 or less at current OR prices.
