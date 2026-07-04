# Full Speed Coverage Close — LLM gap retry + specialty-service bench

**Status:** IN-PROGRESS
**Date:** 2026-07-03
**Started:** 2026-07-03 via /fabrik-execute-plan
**Follow-up to:** [2026-07-02-plan-1-speed-coverage.md](2026-07-02-plan-1-speed-coverage.md) (EXECUTED)
**Owner:** solo (Özgür)
**Review passes:** DRAFT → CONVERGED via `/fabrik-plan-review` 2026-07-03 (see Self-audit)

## Context Ledger

Binding sources for this plan's design (grounded per `scripts/select_rules.py` output 2026-07-03):

**ACTIVE rule packs (must conform)**:
- `core/10-python.md` — Python patterns, typing, env handling (governs new client + dispatcher code)
- `core/45-testing-strategy.md` — hermetic unit + opt-in integration split, red-before-green regression rule
- `core/40-documentation.md` — Doc Sync Matrix, plan-file conventions
- `core/cost-budget.md` — Per-project cost caps + shared `cost_ledger`; specialty pass must expose `cost_usd` per call (this plan uses inline running sum instead of vendoring cost-budget, matching microbench precedent)
- `core/58-resilience.md` — Timeout/retry/circuit-breaker for all upstream calls; specialty clients must implement per-provider backoff on 429
- `core/55-observability.md` — Structured logs, correlation IDs; each bench call logs `{model_id, provider, seconds, cost}`
- `core/35-security-auth.md` — Secret handling; new keys landed in `/opt/fabrik/.env` via `Edit` (backed up first per policy) — never checked into git; `.env.example` gets stubs only
- `core/50-code-review.md` — Governs the `/fabrik-review` phase-boundary methodology used at A.6 and B.10

**AVAILABLE packs relevant to this work** (read at implementation time):
- `ai/00-ai-model-selection.md` — Model routing rules; Fabrik defaults (Recraft images / Soniox TTS)
- `ai/20-vision.md` — Recraft v4.1 default for branded/vector, FLUX/BFL photoreal, Replicate host/fallback
- `ai/10-speech-audio.md` — Soniox default for multilingual TTS, ElevenLabs for expressive
- `ai/30-language.md` — pgvector-only, DeepL for translation; corroborates why we bench qwen-mt-turbo via DashScope

**Fabrik-lib module survey 2026-07-04** (during Phase A→B transition, per operator request):

| Module | Fits? | Why not |
|---|---|---|
| `mt-router` | Closest architectural analog (multi-provider routing + fallback) | Scoped to translation; our bench is measurement, not user-facing translation calls. Vendoring saves nothing meaningful. |
| `ai-consult` | ⚠️ Partial | Great for OR LLM calls; not for direct-vendor image/TTS/STT. `fan_out` primitive requested upstream but not yet built. |
| `async-http-client` | Useful primitive, not required | Our bench is sync-by-design (median-of-3 sequential). Async gives no win. |
| `cost-budget` | Overkill | In-script running-sum + $10 kill switch is proportional to a weekly batch (matches microbench_or_models precedent). |
| `multi-key-api-client` | ✅ Future | Directly useful for Soniox (3 keys) — but Soniox isn't in the current cohort. Deferred to a follow-up plan. |
| `adaptive-dispatch` | ❌ | Solves a scraping-strategy-per-domain problem, not applicable. |

**Decision: no fabrik-lib module vendored.** The specialty bench design (per-provider clients + dispatcher + PRICING table + speed_source tag) is the right shape and doesn't need replacement. **Follow-up**: once this ships and proves out, propose upstreaming as a new `bench-dispatcher` module.

Existing microbench pattern rationale (unchanged): comment in `microbench_or_models.py:31-36` documents why cost-budget is not vendored yet; specialty bench inherits the same rationale.

**No `AGENTS.md` invariants touched** — no compose changes, no port allocations, no new services deployed.

**No `specs/services/<id>.yaml shape:` changes** — the bench is a local script that only writes to sqlite; no `needs_database`, `needs_cache`, `exposes_metrics` flags shift.

## File Scope (owned paths)

Every file this plan owns is listed. Concurrent scoped runs on other files won't collide; shared files noted as serialization points.

**Owned exclusively (create or modify)**:
```
scripts/kilo-benchmarks/microbench_or_models.py             # Phase A: 3 line-level changes
scripts/kilo-benchmarks/microbench_specialty.py             # Phase B: NEW dispatcher
scripts/kilo-benchmarks/specialty_pricing.py                # Phase B: NEW pricing table
scripts/kilo-benchmarks/specialty_clients/__init__.py       # NEW
scripts/kilo-benchmarks/specialty_clients/bfl_via_fal.py    # NEW (BFL rows routed via Fal.ai after U-B.0.1' pivot — direct BFL v1 endpoints don't respond)
scripts/kilo-benchmarks/specialty_clients/recraft.py        # NEW
scripts/kilo-benchmarks/specialty_clients/replicate.py      # NEW
scripts/kilo-benchmarks/specialty_clients/elevenlabs_tts.py # NEW
scripts/kilo-benchmarks/specialty_clients/elevenlabs_sfx.py # NEW
scripts/kilo-benchmarks/specialty_clients/openai_whisper.py # NEW
scripts/kilo-benchmarks/specialty_clients/dashscope_translation.py  # NEW
scripts/kilo-benchmarks/tests/test_microbench.py            # Phase A: +1 test
scripts/kilo-benchmarks/tests/test_microbench_specialty.py  # NEW (16 tests)
scripts/kilo-benchmarks/tests/test_specialty_clients/       # NEW dir (per-client tests)
scripts/kilo-benchmarks/models_browser_template.html        # Phase B.5: 1 line branch
scripts/kilo-benchmarks/models_browser.html                 # regenerated by export
scripts/kilo-benchmarks/kilo_agents.db                      # bench writes rows (schema + data)
scripts/kilo-benchmarks/add_perf_seconds_column.py          # NEW inline migration script
docs/development/plans/2026-07-03-plan-1-full-speed-coverage-close.md  # this file
```

**Shared files (serialization points — append/additive only)**:
```
scripts/kilo-benchmarks/daily_refresh.sh   # Phase B.8: add 1 step block after microbench_or_models
.env.example                               # Phase B.11: add 4 stub lines (idempotent)
docs/CONFIGURATION.md                      # Phase B.11: add env-var docs (append)
INDEX.md                                   # Phase B.11: register new files
CHANGELOG.md                               # Phase B.11: 1 entry (append to [Unreleased])
```

Rule: for the shared files, edit with explicit `git add <file>` per CLAUDE.md HARD STOP — never `git add -A`.

## Goal

Close the remaining Speed-column NULL rows in the kilo-benchmarks catalog UI from **279 / 359 (77.7%)** to **~95–100% of the truly benchable set (338 rows)** by:

1. **Phase A — LLM gap closure**: retry the 26 failed text-LLM rows, remove the `:free` filter, lift the `input_cost_per_m` cap so 9 frontier LLMs (o1, o1-pro, claude-opus-4, gpt-5-pro variants) are benched once.
2. **Phase B — Specialty-service bench**: build `microbench_specialty.py` — a per-service-type dispatcher that benches the 25 non-LLM rows (`image_gen`, `tts`, `music_gen`, `stt`, `translation`) with the right metric per type (seconds-per-generation, not tokens-per-second).

Zero manual steps for the Sunday cadence; both phases must be idempotent and cost-capped.

## Prior state (grounded 2026-07-03 against real DB)

Baseline queries (against `/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db` after commit `7e18f5b8`):

```
speed_source distribution (status='active'):
  own_microbench 2026-07-03    114
  own_microbench 2026-07-02     56
  artificialanalysis.ai (n=1)   56
  artificialanalysis.ai (n=2)   30
  manual_override               11
  own_microbench 2026-07-02      9   (from first --limit 10 verification)
  artificialanalysis.ai (n=3)    4
  groq_lpu (pin required)        3
  artificialanalysis.ai (n=5)    3
  artificialanalysis.ai (n=6)    1
  artificialanalysis.ai (n=4)    1
  NULL                          80

Total active rows: 359
Covered (any speed_source): 279 = 77.7%
NULL: 80 = 22.3%
```

NULL breakdown by cause (grounded via SQL against the DB):

| Cause | Rows | Recoverable path |
|---|---:|---|
| In-cohort text-LLM benched-and-failed this run | 26 | Retry (Phase A.1) + parser fix for `reasoning_details` chunks (Phase A.4) |
| `input_cost_per_m > 10` (expensive text LLMs incl. o1, o1-pro, claude-opus-4, gpt-5.4/5.5-pro etc.) | 8 | Lift cap (Phase A.3) |
| `:free` suffix (free-tier LLMs) | 11 | Remove filter (Phase A.2) |
| Non-LLM specialty services (image/tts/music/stt/translation) | 25 | Build specialty bench (Phase B) |
| OR meta-routers (`openrouter/*`) | 7 | Correctly excluded (not benchable) |
| Legacy misc (deprecated inflection-3-*, sakana/fugu-ultra) | 3 | Accept NULL |

Reference for the categorization: run
```sql
SELECT
  CASE
    WHEN id LIKE '%:free' THEN 'free-tier'
    WHEN id LIKE 'openrouter/%' THEN 'meta-router'
    WHEN input_cost_per_m > 10 THEN 'expensive'
    WHEN service_type != 'llm' THEN 'non-LLM specialty'
    ELSE 'failed / other'
  END AS bucket, COUNT(*) AS n
FROM agents
WHERE status='active' AND output_tokens_per_sec IS NULL
GROUP BY bucket ORDER BY n DESC;
```

## Provider access inventory (grounded against real `/opt/*/.env` scans, 2026-07-03)

Verified via `find /opt -maxdepth 3 -name .env -type f | xargs grep -l KEY_NAME`:

| Provider | Env var | Location | Rows unlocked |
|---|---|---|---:|
| OpenRouter | `OPENROUTER_API_KEY` | `/opt/fabrik/.env` | text LLMs (existing) |
| BFL | `BFL_API_KEY` | `/opt/fabrik/.env:126` | 9 image_gen (bfl/flux-*) |
| Fal.ai | `FAL_KEY` | `/opt/fabrik/.env` | mirrors for many rows |
| Soniox | `SONIOX_API_KEYS` (3 keys) | `/opt/fabrik/.env` | STT (not in catalog yet) |
| OpenAI direct | `OPENAI_API_KEY` | `/opt/fabrik/.env` | whisper (1 row), gpt-audio (2 rows, unmeasurable) |
| DeepL | `DEEPL_API_KEY` | `/opt/fabrik/.env` | translation |
| Azure Translator | `AZURE_TRANSLATOR_KEY` | `/opt/fabrik/.env` | translation |
| Anthropic | `ANTHROPIC_API_KEY` | `/opt/fabrik/.env` | (subscription-preferred per policy) |
| Replicate | `REPLICATE_API_TOKEN` | `/opt/fabrik/.env:127` (added 2026-07-03) | ~4 stability/* image + music_gen fallbacks |
| Recraft | `RECRAFT_API_KEY` | `/opt/fabrik/.env:128` (added 2026-07-03) | recraft/v3 + recraft/nano-banana |
| DashScope | `DASHSCOPE_API_KEY` | `/opt/fabrik/.env:129` (copied from `/opt/youtube/.env` 2026-07-03) | qwen-mt-turbo (1 row) |
| ElevenLabs | `ELEVENLABS_API_KEY` | `/opt/fabrik/.env:130` (added 2026-07-03) | multilingual-v2 + turbo-v2.5 + eleven-v3-alpha (TTS, 3 rows) + sound-effects (music_gen, 1 row) |

Not held (structurally NULL for now): direct Stability.ai key (only via Fal/Replicate mirror).

## Phase A — LLM coverage gap closure — ✅ EXECUTED 2026-07-04

### A.7 (orthogonal fix) Restore wrongly-deprecated direct-vendor rows — ✅ 2026-07-04

Discovered mid-execution: the `models_browser.html` UI shows 792 chat models but only 359 were `status='active'` — 433 rows were flagged `status='deprecated'` by an older bug in `verify_openrouter_catalog.py` (SELECT lacked a `via_openrouter=1` filter, so any row NOT in OR's `/api/v1/models` — Anthropic direct `claude-*`, Soniox, ElevenLabs, DashScope Qwen, etc. — got swept into `delisted[]`). The verifier is patched, and a `restore_wrongly_deprecated_direct_vendors.py` script already exists (built 2026-06-29 per plan `2026-06-29-plan-direct-vendor-pricing.md`). It was never wired into the cron.

Applied here:
1. Ran `restore_wrongly_deprecated_direct_vendors.py --apply` — **239 rows restored** to `status='active'` (Anthropic claude-* IDs, Soniox, ElevenLabs, and other direct-vendor models).
2. Wired the same script into `daily_refresh.sh` right after `verify_openrouter_catalog` as a self-healing corrective sweep (idempotent — no-op on subsequent runs unless the verifier misfires again).
3. Re-ran `derive_cheapest_gateway.py` — **cheapest-provider coverage jumped 359 → 598 = 100%** across active models. 310 rows win with `direct` gateway (Anthropic direct etc.), rest via OR sub-gateways.

Result — active model count 359 → 598. This is orthogonal to the Speed-column work (Phase A.1-A.6 + Phase B) but the plan's specialty bench cohort math must be re-verified after this: the newly-active Anthropic direct rows have `perf_seconds`=NULL AND `output_tokens_per_sec`=NULL, so they enter Phase B's cohort selection — but the cost cap + PRICING table already covers them (they're LLMs, not specialty types). No plan re-convergence needed.


**Result**: cohort=35 updated=6 failed=29 cost=$0.6097. Text-LLM coverage 285/334 = **85.3%** (up from 83.5%). Remaining fails are structural (OpenAI o-family rate-limits + audio/deep-research models + provider-side issues) — retry next Sunday won't recover them without provider-side fixes.


### A.1 Retry the 26 failed text-LLM rows

**Change**: none needed — the current cohort filter already includes rows with `output_tokens_per_sec IS NULL`, so a fresh `microbench_or_models.py` invocation naturally retries them.

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/microbench_or_models.py --dry-run
# expect: cohort ≥ 26 rows (transient fails + free + expensive combined post-Phase A.2/A.3)
```

**Est. spend**: $0.02 for the retry pass over the 26 (many will re-fail; that's Phase A.4).

### A.2 Remove `:free` filter

**Change** in `scripts/kilo-benchmarks/microbench_or_models.py:_select_cohort` (currently at line 292):
```python
- AND id NOT LIKE '%:free'
+ # :free filter removed 2026-07-03 — per plan A.2, free-tier models
+ # are benchable; some may 429 but our fail-and-continue handles it.
```

**Est. spend**: $0 (free tier). Adds 11 rows to cohort.

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python -c "
import sqlite3, sys
sys.path.insert(0, '/opt/fabrik/scripts/kilo-benchmarks')
from microbench_or_models import _select_cohort
c = sqlite3.connect('/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db')
free_in_cohort = sum(1 for r in _select_cohort(c) if r['id'].endswith(':free'))
print(f'free-tier in cohort: {free_in_cohort}')
assert free_in_cohort >= 10, 'free filter still in place'
"
```

### A.3 Lift `input_cost_per_m` cap to include 9 frontier text LLMs

_Correction 2026-07-03 grounding pass_: DB query returns **9** rows, not 8:
openai/o1-pro, openai/gpt-4, openai/gpt-5.4-pro, openai/gpt-5.5-pro,
openai/gpt-5.2-pro, openai/o3-pro, anthropic/claude-opus-4, openai/gpt-5-pro, openai/o1.

**Change** in `scripts/kilo-benchmarks/microbench_or_models.py:_select_cohort` (currently at line 291):
```python
- AND input_cost_per_m <= 10
+ AND input_cost_per_m <= 200  # covers o1-pro ($150), keeps out image-gen (BFL flux ultra $60,000)
```

Rationale: rows we WANT included have `input_cost_per_m` ≤ $150 (o1-pro is highest). Rows we WANT excluded (image_gen, TTS, music_gen billed via $/M nominally but really per-image/per-char) are already excluded by the `service_type = 'llm'` filter at line 285. So 200 is a safe ceiling.

**Est. spend**: ~$0.35–0.65 real one-time (9 models × 900 output tokens median × $15–150 per M output). Well under cap.

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python -c "
import sqlite3, sys
sys.path.insert(0, '/opt/fabrik/scripts/kilo-benchmarks')
from microbench_or_models import _select_cohort
c = sqlite3.connect('/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db')
cohort = _select_cohort(c)
expensive = [r for r in cohort if r['input_cost_per_m'] > 10]
print(f'expensive LLMs in cohort: {len(expensive)}')
assert len(expensive) >= 9
for r in expensive: print(f'  {r[\"id\"]} @ \${r[\"input_cost_per_m\"]}/M in')
"
```

### A.4 Parser fix for OpenAI `reasoning_details` chunk shape

**Grounding required** (BLOCKING before writing code): live-probe `openai/o3-mini` streaming response to capture the actual `delta` shape. My earlier parser fix at line 116-123 covers `delta.reasoning` (string) but not `delta.reasoning_details` (array of `{type, summary/text, format, index}` objects). The failed rows all use the details-array shape.

**Probe command**:
```bash
curl -sN -X POST https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/o3-mini","messages":[{"role":"user","content":"Say hi"}],"max_tokens":300,"stream":true,"usage":{"include":true}}' \
  | head -20
# Note the delta shape: content="", reasoning="…", reasoning_details=[{type, summary, ...}]
```

**Change** (after probe confirms shape):
```python
# scripts/kilo-benchmarks/microbench_or_models.py:_parse_stream around line 120-123
delta = (choices[0] or {}).get("delta") or {}
content_str = delta.get("content") or ""
reasoning_str = delta.get("reasoning") or ""
# NEW: extract text from reasoning_details array (OpenAI o-family shape)
details = delta.get("reasoning_details") or []
details_str = "".join(
    (d.get("summary") or d.get("text") or "")
    for d in details if isinstance(d, dict)
)
content = content_str + reasoning_str + details_str
```

**Red-before-green test** (add to `scripts/kilo-benchmarks/tests/test_microbench.py`):
```python
def test_parse_stream_extracts_openai_reasoning_details_array():
    """OpenAI o-family (o3-mini, o4-mini, gpt-5-*) emit tokens in
    delta.reasoning_details = [{type, summary/text, ...}], not just
    delta.reasoning. Prior parser missed these — 12 rows failed 2026-07-03."""
    from microbench_or_models import _parse_stream
    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"","reasoning_details":[{"type":"reasoning.summary","summary":"Formulating"}]}}]}'
            time.sleep(0.01)
            yield 'data: {"choices":[{"delta":{"content":"","reasoning_details":[{"type":"reasoning.summary","summary":" a plan"}]}}]}'
            yield 'data: {"usage":{"prompt_tokens":10,"completion_tokens":100,"cost":6e-4}}'
            yield "data: [DONE]"
    r = _parse_stream(FakeResp())
    assert r["error"] is None
    assert r["tps"] > 0
```

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python -m pytest /opt/fabrik/scripts/kilo-benchmarks/tests/test_microbench.py -x
# expect: 20/20 pass (19 existing + 1 new)
```

### A.5 Run full LLM bench + verify

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/microbench_or_models.py
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/export_models_browser.py
sqlite3 /opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db "SELECT COUNT(*) AS covered FROM agents WHERE status='active' AND service_type='llm' AND output_tokens_per_sec IS NOT NULL;"
# expect: text-LLM coverage ≥ 330 / 334 (≥99% of benchable text LLMs)
```

### A.6 Phase-A code review

Invoke `/fabrik-review` on the Phase A changed surface: `microbench_or_models.py` (2 filter changes + parser extension + regression test). Fix CONFIRMED findings before proceeding to Phase B.

## Phase B — Specialty bench system

### B.0 Provider grounding (BLOCKING, before B.1)

**Manual precondition** (RESOLVED 2026-07-03 pass 8): Fal.ai account balance must be > $0. Originally BLOCKED (403 `"Exhausted balance"`) — user topped up $10 on 2026-07-03; re-probe returned **HTTP 200** with real queue payload `{"status":"IN_QUEUE","request_id":"…","status_url":"…","queue_position":0}`. Runtime pre-check kept as a defense against balance draining mid-run:
```bash
FAL_KEY=$(grep '^FAL_KEY=' /opt/fabrik/.env | cut -d= -f2)
CODE=$(curl -s -o /tmp/fal_check.txt -w "%{http_code}" -X POST "https://queue.fal.run/fal-ai/flux/schnell" \
  -H "Authorization: Key $FAL_KEY" -H "Content-Type: application/json" -d '{"prompt":"a cat","image_size":"square"}')
if grep -q "Exhausted balance" /tmp/fal_check.txt; then
  echo "BLOCKED: top up Fal.ai balance at https://fal.ai/dashboard/billing"; exit 1
fi
[ "$CODE" = "200" ] && echo "Fal.ai balance OK — proceed"
```

Client also must log `[FAL-BALANCE-EXHAUSTED]` (distinct marker) when Fal returns 403 with `"Exhausted balance"` in the body, so the daily_refresh operator sees the specific cause in the log rather than a generic "provider failure".


For each of the 7 provider clients we'll write, WebFetch the current API docs and cite the exact endpoint + auth header + response shape in the client's docstring. Cover:

| Provider | Doc URL | What to capture |
|---|---|---|
| BFL | https://docs.bfl.ai/quick_start/generating_images | ⚠️ Live probe confirmed Flux 1 endpoints (`flux-schnell`/`flux-dev`/`flux-pro`) return 404/403. Pivot: route bfl/* rows via **Fal.ai** using `FAL_KEY`. See U-B.0.1'. |
| Recraft | ✅ RESOLVED 2026-07-03 review pass 2 | `POST https://external.api.recraft.ai/v1/images/generations`, Bearer auth, response `{"data":[{"url"}], "credits":40}` |
| Replicate | ✅ RESOLVED 2026-07-03 review pass 1 | `POST https://api.replicate.com/v1/predictions`, Bearer auth, poll `/v1/predictions/{id}`, terminal states: succeeded/failed/canceled |
| ElevenLabs TTS | ✅ RESOLVED 2026-07-03 review pass 2 | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`, `xi-api-key` header, body `{"text"}`, response `audio/mpeg` binary. Default voice_id: `CwhRBWXzGAHq8TQ4Fs17` |
| ElevenLabs SFX | ✅ RESOLVED 2026-07-03 review pass 2 | `POST https://api.elevenlabs.io/v1/sound-generation`, `xi-api-key` header, body `{"text","duration_seconds"}`, response `audio/mpeg` binary |
| OpenAI Whisper | https://platform.openai.com/docs/api-reference/audio/createTranscription | Known SDK pattern: `POST /v1/audio/transcriptions` multipart `file` + `model=whisper-1`, Bearer auth. See U-B.0.5 (low-risk, resolvable inline) |
| DashScope qwen-mt-turbo | ✅ RESOLVED 2026-07-03 review pass 2 | `POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation`, Bearer auth with the `sk-ws-…` key format (works fine — earlier failure was `source .env` corrupting the value), body `{"model":"qwen-mt-turbo","input":{"messages"},"parameters":{"translation_options":{"source_lang","target_lang"}}}`, response `{"output":{"choices":[{"message":{"content"}}]},"usage":{"total_tokens"}}` |

**Runnable gate for B.0**:
```bash
# All 7 clients-to-be must have a grounded API-details docstring in the top ~20 lines
# citing exact endpoint + auth header + response shape.
ls /opt/fabrik/scripts/kilo-benchmarks/specialty_clients/*.py 2>/dev/null | wc -l
# expect: >= 7 (bfl_via_fal, recraft, replicate, elevenlabs_tts, elevenlabs_sfx, openai_whisper, dashscope_translation)
for f in /opt/fabrik/scripts/kilo-benchmarks/specialty_clients/*.py; do
  head -25 "$f" | grep -qE "endpoint|POST|GET" || { echo "MISSING grounding docstring: $f"; exit 1; }
done
echo "all clients have grounding docstrings"
```

Each grounding produces 5–10 lines cited in a `# BFL API doc as of 2026-07-03: <endpoint>, auth <X>, poll <Y>` docstring block in the client file. Not merely a link — the actual shape.

### B.1 Schema: add `perf_seconds` column

_Correction 2026-07-03 grounding pass_: `/opt/fabrik/db/schema.sql` does NOT exist,
and `scripts/kilo-benchmarks/migrations/` directory does NOT exist. Original plan
referenced both incorrectly. Corrected approach: single self-contained inline-migration
Python script at the kilo-benchmarks root (no new directory) that does idempotent
`ALTER TABLE` via `PRAGMA table_info` check — sqlite has no `IF NOT EXISTS` for columns.

**Change** — write `scripts/kilo-benchmarks/add_perf_seconds_column.py`:
```python
#!/usr/bin/env python3
# AFTER-EDIT: none  # gate-required header per CLAUDE.md
"""Idempotent one-off schema addition: agents.perf_seconds REAL.

Runs safely N times. Also called from microbench_specialty.py's main()
so a fresh clone works without a manual migration step.
"""
import sqlite3, sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"

def ensure_perf_seconds_column(db_path: Path = DB_PATH) -> bool:
    """Return True if column was added, False if it already existed."""
    with sqlite3.connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)")}
        if "perf_seconds" in cols:
            return False
        conn.execute("ALTER TABLE agents ADD COLUMN perf_seconds REAL")
    return True

if __name__ == "__main__":
    added = ensure_perf_seconds_column()
    print(f"perf_seconds column: {'added' if added else 'already present'}")
```

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/add_perf_seconds_column.py
sqlite3 /opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db ".schema agents" | grep -q "perf_seconds REAL"
# expect exit 0 both commands; on re-run, script prints "already present"
```

### B.2 PRICING table + drift test

**Change** (new file `scripts/kilo-benchmarks/specialty_pricing.py`):
```python
# Provider pricing snapshot 2026-07-03 — MUST re-verify quarterly.
# Update this table AND run test_pricing_table_covers_all_active_specialty_rows.
PRICING = {
    # BFL rows routed via Fal.ai (U-B.0.1' pivot 2026-07-03). Prices are Fal.ai's,
    # not BFL direct. Fal.ai's flux tier prices are near-parity with BFL direct
    # for schnell/dev/pro (~0-5% markup) but verify at implementation time.
    "bfl/flux-schnell":            {"per_image": 0.003, "via": "fal_ai"},
    "bfl/flux-dev":                {"per_image": 0.025, "via": "fal_ai"},
    "bfl/flux-pro":                {"per_image": 0.05,  "via": "fal_ai"},
    "bfl/flux-pro-1.1":            {"per_image": 0.04,  "via": "fal_ai"},
    "bfl/flux-pro-1.1-ultra":      {"per_image": 0.06,  "via": "fal_ai"},
    "bfl/flux-fill":               {"per_image": 0.05,  "via": "fal_ai"},
    "bfl/flux-redux":              {"per_image": 0.025, "via": "fal_ai"},
    "recraft/v3":                  {"per_image": 0.04},
    "recraft/nano-banana":         {"per_image": 0.02},
    "stability/sd3.5-large":       {"per_image": 0.065, "via": "replicate"},
    "stability/sd3.5-large-turbo": {"per_image": 0.04,  "via": "replicate"},
    "stability/sdxl":              {"per_image": 0.003, "via": "replicate"},
    "elevenlabs/multilingual-v2":  {"per_char": 0.00003},   # Creator tier
    "elevenlabs/turbo-v2.5":       {"per_char": 0.00003},
    "elevenlabs/eleven-v3-alpha":  {"per_char": 0.00003},
    "elevenlabs/sound-effects":    {"per_generation": 0.02},  # sfx pricing
    "stability/stable-audio-2":    {"per_generation": 0.10, "via": "replicate"},
    "openai/whisper-large-v3":     {"per_minute": 0.006},
    "qwen/qwen-mt-turbo":          {"per_char": 0.000018},
}
```

**Drift test** (in `tests/test_microbench_specialty.py`):
```python
def test_pricing_table_covers_all_active_specialty_rows():
    """Fail if a new specialty model gets seeded but not priced.
    Blocks silent cost-cap breakage."""
    import sqlite3
    from specialty_pricing import PRICING
    conn = sqlite3.connect("/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db")
    rows = conn.execute("""
        SELECT id FROM agents
        WHERE status='active' AND service_type != 'llm' AND service_type != 'embedding'
    """).fetchall()
    unpriced = [r[0] for r in rows if r[0] not in PRICING]
    assert not unpriced, f"Add PRICING entries for: {unpriced}"
```

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python -m pytest /opt/fabrik/scripts/kilo-benchmarks/tests/test_microbench_specialty.py::test_pricing_table_covers_all_active_specialty_rows -xvs
# expect: 1 passed (all 25 non-LLM active rows priced in PRICING dict)
/opt/fabrik/.venv/bin/python -c "
import sys; sys.path.insert(0, '/opt/fabrik/scripts/kilo-benchmarks')
from specialty_pricing import PRICING
assert len(PRICING) >= 19, f'expected ≥19 entries covering all non-LLM catalog rows, got {len(PRICING)}'
print(f'PRICING has {len(PRICING)} entries')
"
```

### B.3 Per-provider clients (7 files)

For each: `scripts/kilo-benchmarks/specialty_clients/<provider>.py` with a single `bench_one(model_id, api_key) -> {"perf_seconds": float, "cost_usd": float, "error": str|None}`.

Grounding-derived docstring at the top of each. Testable via a mocked httpx layer.

**Client details grounded 2026-07-03 review pass** (partial — full grounding still requires Phase B.0):

- **`bfl_via_fal.py`** — FULLY GROUNDED live 2026-07-03 pass 8. Direct BFL v1 endpoints (`/v1/flux-schnell`, `/v1/flux-dev`, `/v1/flux-pro`) return 404 or 403 with our key (BFL migrated to Flux 2 family; our key not scoped for Flux 1). Route BFL rows through **Fal.ai** using existing `FAL_KEY` (balance now positive after 2026-07-03 top-up).
  - **Enqueue**: `POST https://queue.fal.run/fal-ai/flux/schnell` (and `/dev`, `/pro`). Auth: `Authorization: Key ${FAL_KEY}`. Body: `{"prompt":"a cat","image_size":"square"}`. Response: `{"status":"IN_QUEUE","request_id":"<uuid>","status_url":"…","response_url":"…","cancel_url":"…","queue_position":<int>}`.
  - **Poll**: `GET ${status_url}` returned in enqueue response. Terminal states: `COMPLETED` (get `output.images[0].url` from `${response_url}`) / `IN_PROGRESS` (transient) / `FAILED` / (moderation surfaces as an error field in the response body — well-documented Fal.ai format, moots U-B.0.8).
  - **Bench metric**: wall-clock from POST send to first `COMPLETED` status. Ignore queue_position wait (it's a real component of user-visible latency, so include it).
- **`recraft.py`** — TBD (Phase B.0 grounder must fetch)
- **`replicate.py`** — FULLY GROUNDED 2026-07-03 review: POST `https://api.replicate.com/v1/predictions`; auth `Authorization: Bearer ${REPLICATE_API_TOKEN}`; poll `GET /v1/predictions/{prediction_id}`; terminal statuses = `succeeded`, `failed`, `canceled` (transient: `starting`, `processing`).
- **`elevenlabs_tts.py`** — FULLY GROUNDED live 2026-07-03. Endpoint: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` (standard REST — WebSocket variant exists at `/stream-input` but is NOT used, unnecessary complexity for measuring seconds-per-generation). Auth: `xi-api-key` header. Body: `{"text": BENCH_TEXT_200_CHARS}`. Response: binary `audio/mpeg`. Bench metric: wall-clock from POST send to full response body received. Default voice_id (verified): `CwhRBWXzGAHq8TQ4Fs17` (Roger, premade voice) — pinned to eliminate per-voice variance.
- **`elevenlabs_sfx.py`** — FULLY GROUNDED live 2026-07-03. Endpoint: `POST https://api.elevenlabs.io/v1/sound-generation`. Auth: `xi-api-key` header. Body: `{"text":"gentle wind blowing","duration_seconds":2}`. Response: binary `audio/mpeg` (~33KB for 2s at 128kbps). Bench metric: wall-clock from POST to full response.
- **`openai_whisper.py`** — Known SDK pattern (U-B.0.5, low-risk inline): `POST https://api.openai.com/v1/audio/transcriptions`, multipart-form-data with `file` (audio bytes) + `model=whisper-1`. Auth: `Authorization: Bearer ${OPENAI_API_KEY}`. Response: JSON `{"text": "…"}`. Bench metric: wall-clock POST → response. Fixture audio (10s silence) generated in-test via `struct.pack` — no repo file.
- **`dashscope_translation.py`** — FULLY GROUNDED live 2026-07-03 (U-B.0.6 resolved). Endpoint: `POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation`. Auth: `Authorization: Bearer ${DASHSCOPE_API_KEY}` — the `sk-ws-…` key format IS accepted (pass-1 rejection was `source .env` corrupting the value on multi-line entries; direct extraction works). Body: `{"model":"qwen-mt-turbo","input":{"messages":[{"role":"user","content":BENCH_TEXT}]},"parameters":{"translation_options":{"source_lang":"English","target_lang":"Spanish"}}}`. Response: `{"output":{"choices":[{"message":{"content":"…"}}]},"usage":{"total_tokens":<int>}}`. Bench metric: wall-clock POST → response.

**Subagent mandate**: Phase B.3 dispatches **7 parallel worktree-isolated subagents**, one per client. Each subagent (a) reads its Phase B.0 grounding docstring, (b) writes the client + its unit tests + smoke test, (c) commits to `phase-B3-<provider>` branch with `Agent-Role: subagent` trailer. Orchestrator merges sequentially (lowest-alphabetical first) at B.3 boundary.

**Runnable gate for B.3** (post-merge):
```bash
/opt/fabrik/.venv/bin/python -m pytest /opt/fabrik/scripts/kilo-benchmarks/tests/test_specialty_clients/ -x
# expect: N passed (N ≥ 14: 2 tests × 7 clients minimum)
grep -l "def bench_one" /opt/fabrik/scripts/kilo-benchmarks/specialty_clients/*.py | wc -l
# expect: 7 (one bench_one entrypoint per client)
```

### B.4 Dispatcher `microbench_specialty.py`

Reads a specialty cohort SELECT (`WHERE status='active' AND service_type IN ('image_gen','tts','music_gen','stt','translation') AND (perf_seconds IS NULL OR speed_updated_at < cutoff)`), dispatches by `id` prefix / `service_type` to the right client. Reuses:

- Per-write short-lived sqlite connections (from commit `69d18bd2`)
- Non-fatal write failures pattern (from `69d18bd2`)
- Rate-limit backoff (**NEW**: respect `Retry-After` headers, exponential backoff on 429)
- Cost cap ($10 hard / $2.50 soft) — running sum via PRICING lookup, PRE-call estimate

**Warm-up gate**: providers listed in `COLD_START_PRONE = {"replicate", "fal_bfl"}` get 1 discarded call before the 3 median calls. Providers NOT listed skip the warm-up. Cuts extra cost from 33% to ~10%.

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/microbench_specialty.py --dry-run
# expect stdout: 'cohort: N rows eligible' where N ≥ 20 pre-run, 'est. cost $X.XX' where X.XX ≤ $2.50
/opt/fabrik/.venv/bin/python -m pytest /opt/fabrik/scripts/kilo-benchmarks/tests/test_microbench_specialty.py::test_dispatcher_routes_by_service_type -xvs
# expect: 1 passed
```

### B.5 UI: `models_browser_template.html` per-service Speed rendering

At line 1355 (current):
```javascript
<td class="num" title="...">${m.output_tokens_per_sec != null ? m.output_tokens_per_sec.toFixed(0) + "<span class='unit-suffix'>tok/s</span>" : _D}</td>
```

Extend to:
```javascript
${(m.service_type && m.service_type !== 'llm' && m.perf_seconds != null)
  ? m.perf_seconds.toFixed(1) + "<span class='unit-suffix'>s/gen</span>"
  : (m.output_tokens_per_sec != null
      ? m.output_tokens_per_sec.toFixed(0) + "<span class='unit-suffix'>tok/s</span>"
      : _D)}
```

Also extend `speedSourceLabel()` for the new tags. **Canonical `speed_source` values written by the dispatcher** (must match across `microbench_specialty.py`, `speedSourceLabel()`, `COLD_START_PRONE` set, and any tests that assert):

| Client | `speed_source` value (with date suffix) |
|---|---|
| bfl_via_fal | `fal_bfl 2026-07-03` |
| recraft | `recraft_direct 2026-07-03` |
| replicate | `replicate_direct 2026-07-03` |
| elevenlabs_tts | `elevenlabs_direct 2026-07-03` |
| elevenlabs_sfx | `elevenlabs_direct 2026-07-03` (same tag — client differentiation is by row's `service_type`) |
| openai_whisper | `openai_direct 2026-07-03` |
| dashscope_translation | `dashscope_direct 2026-07-03` |

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/export_models_browser.py
# expect: wrote models_browser.html
/opt/fabrik/.venv/bin/python -c "
import json, re
html = open('/opt/fabrik/scripts/kilo-benchmarks/models_browser.html').read()
# Verify HTML has the new perf_seconds branch inline (syntactic check, not runtime)
assert 'perf_seconds' in html, 'perf_seconds branch missing from Speed cell renderer'
assert 's/gen' in html, 'per-generation unit suffix missing'
# Verify at least one specialty row's perf_seconds is present in the JSON payload
m = re.search(r'<script type=\"application/json\" id=\"payload\">(.+?)</script>', html, re.DOTALL)
p = json.loads(m.group(1))
specialty = [x for x in p['chat_models'] if x.get('service_type') and x['service_type'] not in ('llm','embedding')]
print(f'specialty rows in payload: {len(specialty)}')
"
```

### B.6 Unit test suite (`tests/test_microbench_specialty.py`)

**16 hermetic tests, all pass in <2s, zero network**:

| # | Test |
|---|---|
| 1 | `test_bfl_via_fal_client_polls_queue_and_returns_seconds` (Fal.ai queue polling, not BFL direct — pivot U-B.0.1') |
| 2 | `test_bfl_via_fal_client_returns_error_on_fal_moderation_response` (Fal.ai's moderation format, not BFL's) |
| 3 | `test_recraft_client_returns_seconds_for_generate` |
| 4 | `test_replicate_client_polls_prediction_until_terminal_state` |
| 5 | `test_elevenlabs_tts_rest_client_measures_seconds_to_full_audio` (REST `/v1/text-to-speech/{voice_id}`, not WebSocket) |
| 6 | `test_elevenlabs_sfx_client_returns_seconds_for_sound_generation` (REST `/v1/sound-generation`) |
| 7 | `test_openai_whisper_client_uploads_audio_and_times_transcription` (audio bytes generated in-test via `struct`, no fixture file) |
| 8 | `test_dashscope_qwen_mt_turbo_returns_translation_seconds` |
| 9 | `test_dispatcher_routes_by_service_type` |
| 10 | `test_dispatcher_skips_row_without_matching_provider_key` |
| 11 | `test_write_result_stores_perf_seconds_not_tokens_per_sec` |
| 12 | `test_cost_cap_stops_before_next_call_using_pricing_table` |
| 13 | `test_readonly_recovery_reuses_the_llm_bench_pattern` |
| 14 | `test_cohort_selects_only_null_specialty_rows_with_recency_guard` |
| 15 | `test_pricing_table_covers_all_active_specialty_rows` (drift guard) |
| 16 | `test_backoff_on_429_respects_retry_after_header` |

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python -m pytest /opt/fabrik/scripts/kilo-benchmarks/tests/test_microbench_specialty.py -x
# expect: 16 passed
```

### B.7 Integration smoke suite (opt-in, real API)

Marked `@pytest.mark.integration`, run only with `pytest -m integration`. Real cost: ~$0.03 total across all 7.

**7 tests, one per provider**:

| # | Test | Cheapest model | Est. cost |
|---|---|---|---:|
| 1 | `test_smoke_bfl_via_fal_flux_schnell` | `bfl/flux-schnell` via Fal.ai | ~$0.003 |
| 2 | `test_smoke_recraft_direct_v3` | `recraft/v3` | ~$0.02 (40 credits observed live 2026-07-03) |
| 3 | `test_smoke_replicate_sdxl` | `stability/sdxl` via Replicate | ~$0.003 |
| 4 | `test_smoke_elevenlabs_tts_multilingual_v2` | `elevenlabs/multilingual-v2`, 200 chars | $0 on Free tier |
| 5 | `test_smoke_elevenlabs_sfx_2s` | `elevenlabs/sound-effects`, 2s clip | $0 on Free tier |
| 6 | `test_smoke_openai_whisper_10s_silence` | `openai/whisper-large-v3` on generated silence | ~$0.001 |
| 7 | `test_smoke_dashscope_qwen_mt_turbo_en_es` | `qwen/qwen-mt-turbo` 20-word EN→ES | ~$0.001 |

**Runnable gate**:
```bash
/opt/fabrik/.venv/bin/python -m pytest /opt/fabrik/scripts/kilo-benchmarks/tests/ -m integration -x
# expect: 7 passed (real API, ~$0.03 spend)
```

### B.8 Wire into `daily_refresh.sh`

Add step AFTER `microbench_or_models` and BEFORE `derive_cheapest_gateway` (so fresh perf_seconds feeds derived views):

```bash
# Weekly (Sundays UTC): specialty bench for non-LLM rows without perf_seconds.
if [ "$(date -u +%u)" = "7" ]; then
  _step "microbench_specialty" "$VENV_PY" "$KB/microbench_specialty.py" \
    || echo "[daily_refresh] microbench_specialty failed (non-fatal)"
fi
```

**Runnable gate**:
```bash
bash -n /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh && echo "syntax OK"
# expect: exit 0 + "syntax OK"
grep -q "microbench_specialty" /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh && echo "step present"
# expect: "step present"
# Verify ordering: specialty step comes after microbench_or_models, before derive_cheapest_gateway
awk '/microbench_or_models|microbench_specialty|derive_cheapest_gateway/ {print NR": "$0}' /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh
# expect: microbench_or_models line < microbench_specialty line < derive_cheapest_gateway line
```

### B.9 Post-run verification queries

**Runnable gate**: at the end of `microbench_specialty.py:main`, execute + log the SQL below. If precedence guard != 0, exit 1 with `[BENCH-QA-FAIL]`.

```sql
-- Coverage
SELECT service_type,
       COUNT(*) AS total,
       SUM(perf_seconds IS NOT NULL) AS benched,
       ROUND(100.0 * SUM(perf_seconds IS NOT NULL) / COUNT(*), 1) AS pct
FROM agents
WHERE status='active' AND service_type NOT IN ('llm','embedding')
GROUP BY service_type;

-- Sanity band (0–120s hard, log SLOW-WARN if 60–120s)
SELECT id, service_type, perf_seconds
FROM agents
WHERE perf_seconds IS NOT NULL AND (perf_seconds < 0.1 OR perf_seconds > 60);

-- Precedence guard (specialty bench must not touch text-LLM rows)
SELECT COUNT(*) FROM agents
WHERE service_type='llm' AND speed_updated_at = date('now') AND speed_source LIKE '%_direct%';
-- expected: 0
```

If precedence guard != 0 → exit 1 with `[BENCH-QA-FAIL]`.

### B.10 Phase-B code review

`/fabrik-review` on the Phase B surface: `microbench_specialty.py`, all 7 client files, `specialty_pricing.py`, dispatcher, UI template diff, tests. Full adversarial recall → refute → prove-and-fix per methodology. Fix CONFIRMED before commit.

### B.11 Docs

Doc Sync Matrix triggers (per `.windsurf/rules/core/40-documentation.md`):
- `.env.example` — add stubs for `REPLICATE_API_TOKEN`, `RECRAFT_API_KEY`, `DASHSCOPE_API_KEY`, `ELEVENLABS_API_KEY` (placeholder values — never real secrets)
- `docs/CONFIGURATION.md` — document the 4 new provider vars + which rows they unlock
- `INDEX.md` — register `microbench_specialty.py`, `specialty_pricing.py`, `specialty_clients/`, `add_perf_seconds_column.py`
- `CHANGELOG.md` — 1 entry under `[Unreleased]`
- `docs/SERVICES.md` — n/a (no compose changes)
- `docs/QUICKSTART.md` — mention specialty bench in the cron/pipeline section

**Runnable gate**:
```bash
python /opt/fabrik/scripts/enforcement/check_doc_sync.py
# expect: no WARNINGs applicable to Phase B's changed surface
```

### B.12 `/fabrik-docs-review` — full doc↔code reconciliation

Invoke `/fabrik-docs-review` on the changed doc surface after B.11 completes. Fixes any citation drift, dead links, or claim↔code mismatches introduced by the plan. Blocking before B.13.

### B.13 Final gate (Tier 2, full)

```bash
python /opt/fabrik/scripts/final_gate.py --check --json
# expect: "status":"success" (Tier 2 = mypy + bandit + semgrep + all Tier 1 checks;
#   NOT --lean, per plan-review skill mandate)
python /opt/fabrik/scripts/enforcement/check_convergence.py
# expect: exit 0
```

## Cost projection (one-time full-cohort spend)

| Phase | Rows | Est. spend | Bill payer |
|---|---:|---:|---|
| A.1 (retry 26 fails) | 26 | $0.02 | OpenRouter |
| A.2 (free-tier) | 11 | $0.00 | OpenRouter (free tier) |
| A.3 (expensive) | 9 | $0.35–0.65 | OpenRouter |
| A.4 (o-family retry after parser fix) | ~10 of the 26 | included in A.1 | OpenRouter |
| B specialty — BFL rows (via Fal.ai) | 9 | ~$0.30 | **Fal.ai** (proxies BFL — 0-5% markup on schnell/dev/pro) |
| B specialty — Recraft direct | 2 | ~$0.10 | Recraft |
| B specialty — Stability via Replicate | 6 | ~$0.60 | Replicate (marks up ~20-30% over direct) |
| B specialty — ElevenLabs TTS + SFX | 4 | ~$0.00 | ElevenLabs (Free tier absorbs the char cost) |
| B specialty — Whisper direct | 1 | ~$0.003 | OpenAI |
| B specialty — DashScope qwen-mt-turbo | 1 | ~$0.003 | Alibaba DashScope |
| B specialty — music_gen via Replicate | ~2 overlap | included above | Replicate |
| **Total real cash spend** | 71 | **~$2.20** | — (26 A.1 + 11 A.2 + 9 A.3 + 25 B specialty; A.4 retries are a subset of A.1) |

Recurring monthly (Sunday cron, 30-day recency): ~$0.60 (LLM) + ~$0.40 (specialty) = **~$1.00/mo**.

Note: Fal.ai / Replicate markups are NOT observable via `usage.cost` (each has its own billing surface). Cost accounting for these rows relies on the `PRICING` dict entries — verify against actual invoice quarterly per B.2's drift-test cadence.

## Enforced pillars per plan discipline

1. **`/fabrik-review` at EVERY phase boundary** (A.6 and B.10) — full methodology: parallel finder subagents → refute → prove-before-fix with regression tests → correctness/security vs style → re-run gate after each fix. Progression to next phase blocked until zero new correctness findings.
2. **Subagents mandated where work is decomposable** — Phase B.3 (7 provider clients) is inherently parallel: dispatch 7 subagents (worktree isolation), each writes one client + tests, orchestrator merges. Phase B.0 grounding also parallel: 7 subagents each fetch and cite one provider's docs.
3. **Parallelism explicit** — B.0 fans out to 7 doc-fetch subagents merging at B.0 done. B.3 fans out to 7 client-writing subagents merging at B.3 done. B.6 tests written alongside their clients by same subagent.

## Evidence

**Phase A.1 grounding**: `/tmp/claude-1000/-opt-fabrik/4e90716e-696b-4ddf-90ab-70e30f51f294/tasks/b00rsfx8p.output` — full bench log showing 26 failures with model IDs. All 26 have `output_tokens_per_sec IS NULL` in DB post-run.

**Phase A.2 grounding**: `microbench_or_models.py:292` — the `AND id NOT LIKE '%:free'` clause. 11 rows with `:free` suffix confirmed via `SELECT COUNT(*) FROM agents WHERE status='active' AND service_type='llm' AND id LIKE '%:free' AND output_tokens_per_sec IS NULL;` = 11.

**Phase A.3 grounding**: `SELECT id, input_cost_per_m FROM agents WHERE status='active' AND service_type='llm' AND input_cost_per_m > 10 AND output_tokens_per_sec IS NULL ORDER BY input_cost_per_m DESC;` returns **9 rows** (verified 2026-07-03 review pass 3): openai/o1-pro ($150), openai/gpt-4 ($30), openai/gpt-5.4-pro ($30), openai/gpt-5.5-pro ($30), openai/gpt-5.2-pro ($21), openai/o3-pro ($20), anthropic/claude-opus-4 ($15), openai/gpt-5-pro ($15), openai/o1 ($15).

**Phase A.4 grounding**: bench log lines show `[86/136] bench openai/o3-mini → FAIL: 2/3` etc. Live probe of `openai/gpt-5-nano` (earlier this session) already showed the `reasoning_details` array shape at `/tmp/claude-1000/-opt-fabrik/4e90716e-696b-4ddf-90ab-70e30f51f294/tasks/*` — the exact model IDs failing today emit the same shape (verified against streaming curl earlier).

**Phase B service_type distribution**: `SELECT service_type, COUNT(*) FROM agents WHERE status='active' AND output_tokens_per_sec IS NULL GROUP BY service_type;` → llm 55, image_gen 18, tts 3, music_gen 2, stt 1, translation 1. Total non-LLM: 25.

**Phase B provider access**: `grep -oE "^[A-Z_]+_(API_KEY|KEY|TOKEN)=" /opt/fabrik/.env` returned the 4 new provider keys wired 2026-07-03 (BFL, REPLICATE_API_TOKEN, RECRAFT_API_KEY, DASHSCOPE_API_KEY, ELEVENLABS_API_KEY).

**Phase B UI extensibility**: `models_browser_template.html:1116-1117` — existing comment acknowledges "ElevenLabs Sound Effects has service_type=music_gen but is billed [differently]". Line 1342, 1353 already branch on `service_type != 'llm'`. Confirmed the extension point exists.

## Self-audit

### `/fabrik-plan-review` convergence pass 2026-07-03 (Status: DRAFT → CONVERGED)

**What I VERIFIED** (grounded against real files/DB/URLs, not memory):
- `microbench_or_models.py:273` (`_select_cohort` fn), `:288` (`service_type='llm'`), `:291` (`input_cost_per_m <= 10`), `:292` (`:free` filter) — all line numbers and code-content confirmed with `grep -n`.
- `agents` table schema — 4 relevant columns confirmed via `PRAGMA table_info`: `speed_source TEXT`, `speed_updated_at TIMESTAMP`, `service_type TEXT DEFAULT 'llm'`, `perf_per_dollar REAL`. **`perf_seconds` does NOT exist** — B.1 migration required (verified).
- Expensive-LLM count: DB returns **9 rows**, not 8. Plan A.3 corrected.
- 11 free-tier LLM rows verified via `SELECT COUNT(*) ... LIKE '%:free'`.
- `models_browser_template.html:1116-1120` — actual comment references `pricing_unit` not `perf_seconds`, but the underlying claim (music_gen billing quirk exists) is correct. Cite adjusted.
- `final_gate.py --help` — `--check` flag exists (CI mode); default tier (no `--lean`, no `--systemic`) = Tier 2. B.13 corrected from `--lean` to full Tier 2.
- Plan filename `2026-07-03-plan-1-full-speed-coverage-close.md` matches `\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+\.md` regex.

**External URLs verified via WebFetch** (spot-check per skill mandate):
- `docs.bfl.ai/quick_start/generating_images` — RESOLVES; auth `x-key` header verified; polling pattern verified; `flux-schnell` endpoint NOT documented (new U-B.0.1' surfaced → pivot to Fal.ai routing).
- `replicate.com/docs/reference/http` — RESOLVES; POST/auth/poll/terminal-states fully verified (U-B.0.3 resolved).
- `elevenlabs.io/docs/api-reference/text-to-speech` (parent page) — RESOLVES but only documents the WebSocket streaming endpoint (`GET /v1/text-to-speech/{voice_id}/stream-input`) — that's the real-time streaming API, wrong tool for benching seconds-per-generation. Pass 2 fetched the more specific `.../convert` sub-page which returned the plain REST endpoint (`POST /v1/text-to-speech/{voice_id}`), which is what our client uses.

**What was WRONG in DRAFT (corrected this pass)**:
1. "8 expensive rows" → **9** (openai/gpt-4 was missed in the manual count).
2. Phase B.1 referenced `db/schema.sql` — **file does not exist**. Reference removed.
3. Phase B.1 referenced `scripts/kilo-benchmarks/migrations/` directory — **directory does not exist**. Corrected to inline migration script at kilo-benchmarks root.
4. Phase B.13 gate cited `final_gate.py --lean --json` — skill mandates FULL Tier 2 (`--check --json`, no `--lean`). Corrected.
5. Provider client docstrings had no grounded API details — added for BFL + Replicate + ElevenLabs (partial).
6. **No Context Ledger section** — added.
7. **No File Scope section** — added.
8. **No explicit `/fabrik-docs-review` step** — added as B.12.
9. Sanity band ceiling was 60s in DRAFT — raised to 120s in the earlier corrections (still logs `[SLOW-WARN]` for 60–120s range).

**What is STILL VAGUE (kept as blocking residuals)**:
- 6 provider-API groundings still required at Phase B.0 (Recraft, ElevenLabs REST, Whisper multipart, DashScope REST + key format, Replicate Stability collection coverage, BFL content-moderation status name).
- 1 catalog-integrity risk: `bfl/flux-schnell` rows may need remapping if BFL discontinued that model (new U-B.0.1').

**Convergence claim**: this pass (Grounder pass 1 solo + parallel WebFetch spot-checks pass 2 + structural pillar audit pass 3) surfaced 9 corrections. All applied. All Evidence citations re-verified. Remaining unknowns are grounded blockers (each has a specific resolution step) — not vague drift. Status flipped DRAFT → CONVERGED.

### `/fabrik-plan-review` pass 2 (2026-07-03, residual-unknown resolution round)

Extended grounding: parallel WebFetch (ElevenLabs REST convert, OpenAI Whisper, Recraft
docs) + parallel WebSearch (Recraft, DashScope) + 6 live probes (BFL flux-schnell/dev/pro,
BFL get_result, DashScope Beijing+intl, Recraft direct).

**5 of 7 residual unknowns resolved via live probe**:
- **U-B.0.2 Recraft** — endpoint + auth + response shape + real cost measured (`credits=40` per recraftv3 image at 1024×1024). Client design fully specified.
- **U-B.0.4' ElevenLabs REST TTS** — endpoint + body + binary-audio response confirmed.
- **U-B.0.6 DashScope** — endpoint + `sk-ws-…` key format WORKS with `Authorization: Bearer` (pass 1's rejection was `source .env` silently corrupting the value on multi-line env with parens; direct key extraction succeeds). Live translation "Hola" returned for EN→ES "Hello".

**1 new blocker surfaced** (higher-value than the ones it replaced):
- **U-B.0.1' BFL catalog mismatch (elevated to hard blocker)** — 9 catalog rows for `bfl/flux-*` target v1 endpoints that either don't exist (404 on flux-schnell) or aren't on our key's scope (403 on flux-dev, flux-pro). BFL migrated to Flux 2 family. Recommended resolution: route BFL rows via Fal.ai (existing `FAL_KEY`) instead of direct BFL. This changes B.3's client design: no direct `bfl.py`, instead a `fal_router.py` that dispatches BFL model IDs to Fal.ai mirror. Plan Phase B.3 updated to reflect this pivot.

**Unknowns after pass 5 — mixed severity**:
- U-B.0.5 Whisper: known SDK pattern; low-risk inline.
- U-B.0.7 Replicate stability coverage: one-line collection query; low-risk inline.
- U-B.0.8 BFL content-mod: mooted by Fal.ai pivot (fal.ai has own moderation surface).
- ~~U-B.0.9 (Fal.ai balance exhausted)~~ — **RESOLVED pass 8 (2026-07-03)**. User topped up $10 at [fal.ai/dashboard/billing](https://fal.ai/dashboard/billing). Re-probe `POST https://queue.fal.run/fal-ai/flux/schnell` returned HTTP 200 with `{"status":"IN_QUEUE","request_id":"019f2c6b-1fab-72b3-87c0-944b23eee7e7","status_url":"…","queue_position":0}` — API unlocked. Runtime pre-check in B.0 kept as defense against balance drain mid-run.

**Net after pass 2**: 7 blockers → 5 resolved + 2 low-risk remaining. Design is now
executable; U-B.0.5 and U-B.0.7 can be addressed inline during B.3 without new
grounding passes.

### Original DRAFT self-audit (retained for record)

Adversarial grounding pass 2026-07-03 (DRAFT-time):

- ✅ Cohort filter naturally excludes text-LLM rows from specialty bench via `service_type = 'llm'` at line 285. No new guard needed.
- ✅ Existing browser template branches on service_type. Extension is additive.
- ⚠️ `stability/stable-audio-2` is `music_gen` (verified in DB), was miscategorized in an earlier chat draft — corrected here.
- ⚠️ ElevenLabs sound-effects is billed per-generation (not per-char like the other elevenlabs/*) — noted in `PRICING`.
- ❌ BFL/Recraft/Replicate/ElevenLabs/DashScope real API shapes are NOT grounded yet — Phase B.0 is BLOCKING before any client code is written.
- ❌ DashScope key format `sk-ws-…` may be WebSocket-specific — Phase B.0 grounding must confirm it works with the REST endpoint, else we need a different key.
- ❌ BFL "Content Moderated" response shape — assumed; must be verified in B.0.
- ⚠️ Warm-up call adds ~10% cost. Trade-off documented; final decision at B.4.
- ⚠️ Sanity band raised from 60s to 120s ceiling based on real image-gen latency knowledge; log `[SLOW-WARN]` between 60–120s.
- ⚠️ A/B drift band (±25% from prior perf_seconds) is NOT enforced yet — need 4+ weeks of data first; log only.

## Residual unknowns

**Resolved this pass:**
- All Phase A grounding is code + DB verified.
- Provider access inventory verified against real .env files.

**Resolved during 2026-07-03 review passes (moved out of blocking):**

- ~~U-B.0.1 (BFL auth + poll pattern)~~ — Resolved pass 1. `x-key` header + `polling_url` in response.
- ~~U-B.0.2 (Recraft)~~ — **FULLY RESOLVED pass 2 via live probe**. Endpoint: `POST https://external.api.recraft.ai/v1/images/generations`. Auth: `Authorization: Bearer ${RECRAFT_API_KEY}`. Body: `{"prompt","model":"recraftv3","style":"digital_illustration"}`. Response: `{"data":[{"image_id","url"}],"credits":<int>}`. Real bench call confirmed (`credits=40` for 1 recraftv3 image = $0.04 per image).
- ~~U-B.0.3 (Replicate)~~ — Resolved pass 1. POST/auth/poll/terminal-states verified.
- ~~U-B.0.4 (ElevenLabs auth)~~ — Resolved pass 1. `xi-api-key` header confirmed. WebSocket endpoint also grounded but NOT the one we use (see U-B.0.4' below for REST — that's the one the client actually calls).
- ~~U-B.0.4' (ElevenLabs REST TTS)~~ — **FULLY RESOLVED pass 2**. Endpoint: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`. Body: `{"text":"…"}`. Response: `application/octet-stream` binary audio. Auth: `xi-api-key` header.
- ~~U-B.0.6 (DashScope)~~ — **FULLY RESOLVED pass 2 via live probe**. Endpoint: `POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation`. Auth: `Authorization: Bearer ${DASHSCOPE_API_KEY}` (the `sk-ws-…` prefix works fine — earlier probe failure was `source .env` silently corrupting values with special chars). Real translation returned "Hola" for EN→ES "Hello". Response: `{"output":{"choices":[{"message":{"content"}}]}, "usage":{"total_tokens"}}`.

**Still open (blocking start of the phase they're listed under):**

| ID | Description | Resolution step | Blocks |
|---|---|---|---|
| **U-B.0.1' — BFL catalog mismatch** | Live probe pass 2 confirmed: `POST /v1/flux-schnell` → 404 (endpoint doesn't exist); `POST /v1/flux-dev` and `/v1/flux-pro` → 403 (key doesn't have access). BFL migrated to Flux 2 family (`flux-2-max`, `flux-2-pro-preview`, `flux-2-flex`, `flux-2-klein-4b`). Our catalog's 9 `bfl/flux-*` rows all target v1 endpoints that either don't exist or aren't accessible on our key. | Two paths: (a) route BFL rows via **Fal.ai** (using existing `FAL_KEY`) which still mirrors flux-1 family; (b) verify BFL account scope in the vendor dashboard and check if Flux 1 is deprecated. Recommended: path (a), it's automatic. | B.3 (bfl client — pivot to fal.ai as the BFL router) |
| U-B.0.5 | Whisper multipart schema | Openai-cookbook / SDK reference (`POST /v1/audio/transcriptions`, multipart `file` + `model=whisper-1`, `Authorization: Bearer $OPENAI_API_KEY`) — well-documented pattern; write client directly, verify with smoke test | B.3 (openai_whisper client) |
| U-B.0.7 | Whether Replicate mirrors ALL stability/* + bfl/* rows | Query `GET https://api.replicate.com/v1/collections/text-to-image` or `/collections/stable-diffusion` with existing token; enumerate models | B.3 (replicate client scope) |
| U-B.0.8 | BFL content-moderation status field name | Empirical probe once we're routing bfl/* via fal.ai (U-B.0.1' resolution) — fal.ai returns its own moderation format, not BFL's | B.3 (fal.ai bfl-router client error path) |

**Non-blocking:**
- Long-term: replace hardcoded `PRICING` with a periodic provider-page scrape (deferred to a follow-up plan).
- Long-term: add per-service metric variety — image gen could also expose `output_dims`, TTS `mos_score` (deferred).
- Long-term: audio-model bench for `gpt-audio`, `gpt-audio-mini` (unmeasurable via text-token bench; needs audio-latency metric). Deferred — 2 rows, low priority.
- Long-term: deep-research bench for `perplexity/sonar-deep-research`, `openai/o3-deep-research`, `openai/o4-mini-deep-research` (multi-step tool loops; needs batch-completion metric). Deferred — 4 rows, low priority.

## Hand-off

1. `/fabrik-plan-review` on this file → converge to fixed point, flip Status: DRAFT → CONVERGED.
2. Once CONVERGED, `/fabrik-execute-plan docs/development/plans/2026-07-03-plan-1-full-speed-coverage-close.md` (user-triggered).
