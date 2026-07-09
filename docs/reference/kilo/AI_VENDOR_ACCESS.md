Last verified: 2026-07-09

# AI Vendor Access — Özgür's Reachable Set

Single source of truth for which vendors the operator can call today. Hand-edited (not auto-generated). The specialty-catalog seeder (`scripts/kilo-benchmarks/seed_specialty_catalog.py`) parses this file to set `agents.reachable_with_existing_keys` (1 = accessible, 0 = new-vendor / needs signup). Rows with Status ✅ or ⚠️ are accessible (⚠️ = accessible but low balance — pick a ✅ peer if one is on the Pareto frontier).

## Column contract

- **Vendor** — human name.
- **DB provider(s)** — comma-separated list of `agents.provider` values (EXACT match — the seeder splits on `,` and strips whitespace).
- **Auth mechanism** — how the key is stored / injected.
- **Status** — one of `✅` (accessible), `⚠️` (accessible, low balance / subscription-only), `❌` (not accessible, needs signup or deprecated).
- **Credits/quota** — current balance or tier.
- **Notes** — non-load-bearing detail (e.g. deprecation notice).

## LLM gateways

| Vendor | DB provider(s) | Auth mechanism | Status | Credits/quota | Notes |
|---|---|---|---|---|---|
| OpenRouter | openai, anthropic, google, x-ai, meta-llama, qwen, deepseek, mistralai, moonshotai, z-ai, minimax, bytedance-seed, microsoft, nvidia, hexgrad, canopylabs, zyphra, sesame | env `OPENROUTER_API_KEY` | ✅ | credits pool | Primary LLM gateway. 5.5% fee + $0.80 min credit-purchase; no per-token markup. Dual-routed with Kilo for most models. |
| Kilo CLI | (peer gateway — same `provider` values as OpenRouter) | subscription (Kilo CLI login) | ✅ | subscription-billed | Peer gateway to OpenRouter. Pick per-model by whichever bake-off row shows the cheaper rate. |
| Claude Max (direct via Claude Code) | anthropic | Claude Code OAuth (`~/.claude/` credentials) | ✅ | Max subscription | Operational path only (sysadmin, watchdog, plan execution). NOT for `fabrik ai generate` content utilities. |

## Specialty vendors (image / TTS / STT / translation)

| Vendor | DB provider(s) | Auth mechanism | Status | Credits/quota | Notes |
|---|---|---|---|---|---|
| Replicate | stability, bfl-via-replicate, recraft-ai | env `REPLICATE_API_TOKEN` | ✅ | credits pool | Official-model route for BFL (FLUX) via Replicate; also stability + Recraft. |
| Fal.ai | bfl | env `FAL_KEY` | ✅ | credits pool | BFL FLUX via Fal — often cheaper than direct BFL. |
| BFL direct | (none — deprecated) | env `BFL_API_KEY` (unset) | ❌ | none | Deprecated per AFCL: Replicate + Fal cover FLUX cheaper. Do NOT recommend a `bfl-direct` route. |
| Recraft direct | recraft | env `RECRAFT_API_KEY` | ✅ | small credits | Direct route for Recraft models when Replicate charges more. |
| Soniox | soniox | env `SONIOX_API_KEY` (3 keys rotated) | ✅ | 3-key rotation | Primary STT vendor — Universal-2 quality tier. |
| ElevenLabs | elevenlabs | env `ELEVENLABS_API_KEY` | ✅ | free tier (10K chars/mo) | Primary TTS vendor for expressive voices. Free tier is enough for dev; watch quota. |
| Alibaba DashScope | qwen, qwen-mt-turbo | env `DASHSCOPE_API_KEY` | ✅ | credits pool | Qwen inference + qwen-mt-turbo translation specialist route. |
| SiliconFlow | qwen, deepseek, z-ai, moonshotai, minimax, tencent, google, bfl, black-forest-labs, meituan-longcat, stepfun, nex-agi, wan-ai, inclusionai, bytedance-seed, indexteam, fishaudio, funaudiollm, tongyi-mai, openai | env `SILICONFLOW_API_KEY` | ✅ | credits pool | 72-model gateway on international endpoint `api.siliconflow.com` (NOT `.cn` — different key domain). Covers LLMs (Qwen 2.5→3.6 line, DeepSeek V3/V4, GLM 4.5→5.2, Kimi K2.5-2.7, MiniMax M2.5/M3, Tencent Hunyuan+Hy3, gemma-4, gpt-oss-20b/120b), image gen (all FLUX + Qwen-Image + Wan2.2 + Z-Image-Turbo), TTS (fish-speech-1.5, IndexTTS-2, CosyVoice2), embeddings (Qwen3-Embedding 0.6B/4B/8B), rerankers (Qwen3-Reranker 0.6B/8B). Full list: `python scripts/kilo-benchmarks/scrape_siliconflow_catalog.py` (also flips `via_siliconflow=1` on affected agents rows). |
| ModelScope | qwen, deepseek, z-ai, moonshotai, minimax, mistralai, stepfun, nex-agi, meituan-longcat, baidu, xiaomi, tencent, shanghai-ai-lab, alibaba-iic, llm-research, medaibase, musepublic, opencompass, opengvlab, xgenerationlab | env `MODELSCOPE_API_KEY` | ✅ | credits pool | 55-model Alibaba model-hub gateway on `https://api-inference.modelscope.cn/v1` (OpenAI-compatible). **Delivered** (via_modelscope=1 in DB): ZhipuAI GLM direct (GLM-5 / 5.1 / 5.2 / 5-Turbo), Tencent Hunyuan Hy3, Xiaomi MiMo-V2-Flash, plus 26 Qwen/DeepSeek/MiniMax/Kimi/stepfun/moonshotai overlap rows = 32 total. **Fetched but unmatched** (awaits new-row ingestion — plan-2 scraper is flip-only, not INSERT): Shanghai AI Lab Intern-S1/S1-mini/S2-Preview, PaddlePaddle ERNIE-4.5-PT (0.3B / 21B-A3B / 300B-A47B / VL-28B — PT = post-training checkpoints, not the DB's Instruct routes), XiYanSQL, IIC GUI-Owl, LLM-Research Llama-4-Maverick, MedAIBase, MusePublic Qwen-Image-Edit, OpenGVLab InternVL3.5-241B, OpenCompass. Format: `ms-*`. Full list: `python scripts/kilo-benchmarks/scrape_modelscope_catalog.py` (also flips `via_modelscope=1` on affected agents rows). |
| Anthropic direct API | anthropic | env `ANTHROPIC_API_KEY` | ⚠️ | subscription-billed via Claude Code | Kept for `fabrik ai generate` content utilities only — never for operational paths (those use Claude Max via Claude Code OAuth). |

## Direct-API vendors — need signup + payment method (not currently reachable)

| Vendor | DB provider(s) | Auth mechanism | Status | Credits/quota | Notes |
|---|---|---|---|---|---|
| OpenAI direct | (none — routed via OpenRouter today) | env `OPENAI_API_KEY` (unset) | ❌ | needs signup | OpenRouter route is cheaper + no separate signup; direct only if a route is OR-blocked. |
| Google Cloud (Gemini API) | (none — routed via OpenRouter today) | GCP service account (unset) | ❌ | needs signup | Gemini API via OpenRouter today; direct only for GCP-only features (grounding, live). |
| Azure OpenAI | (none) | Azure AAD (unset) | ❌ | needs signup | No compelling reason today — OpenRouter covers the model set. |
| Deepgram | (none — no `deepgram` rows in DB yet) | env `DEEPGRAM_API_KEY` (unset) | ❌ | needs signup | Would compete with Soniox for STT; only signup if Soniox 3-key rotation exhausts. |
| AssemblyAI | (none) | env `ASSEMBLYAI_API_KEY` (unset) | ❌ | needs signup | Universal-2 is comparable-quality; not needed while Soniox is up. |
| DeepL | (none — no `deepl` rows in DB yet) | env `DEEPL_API_KEY` (unset) | ❌ | Free tier available (500K chars/mo) | Excellent translation quality; the free tier is enough for dev-scale, but not yet wired. Signup is cheap — flag as an upsell candidate. |

## Web-only accounts — NOT accessible for CLI / API use

| Vendor | DB provider(s) | Auth mechanism | Status | Credits/quota | Notes |
|---|---|---|---|---|---|
| Gemini (web) | (none) | web login only | ❌ | web-tier | UI-only account — do NOT recommend a `google/gemini-*` route on the assumption we can call it; use the OpenRouter route or DashScope. |
| GPT (web / ChatGPT Plus) | (none) | web login only | ❌ | Plus subscription | UI-only account — do NOT recommend a `openai/gpt-*` direct route on this basis; the OpenRouter route is the actual reachable one. |
| Perplexity (web) | (none) | web login only | ❌ | Pro subscription | UI-only account — no API is wired. |
