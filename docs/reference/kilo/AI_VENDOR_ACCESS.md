Last verified: 2026-07-07

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
