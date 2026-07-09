Last verified: 2026-07-09

# Aggregator / Gateway Signup Roadmap

Hand-authored companion to `AI_VENDOR_ACCESS.md` (which lists vendors WIRED today) and to `CANDIDATE_SIGNUPS.md` (auto-generated per-model watchlist from `agents.reachable_with_existing_keys=0`). This file lists **aggregator-tier vendors we've researched as worth signing up for NEXT**, ranked by `(new capability × ease of signup × operator effort)`.

Currently wired (see `AI_VENDOR_ACCESS.md`):
- **OpenRouter** — primary LLM gateway (18 provider families, 347 active models)
- **Kilo CLI** — peer gateway to OR (subscription-billed, dual-routes with OR on 345 models)
- **SiliconFlow** — 72-model LLM/image/TTS/embedding gateway (wired 2026-07-09)
- **Alibaba DashScope** — Qwen-MT-Turbo specialist route
- **Replicate + Fal.ai** — FLUX image gateways
- **Soniox** — primary STT
- **ElevenLabs** — primary TTS (expressive voices)

## Column contract

- **Vendor** — human name.
- **Signup effort** — `trivial` = email + credit card, US OK; `mid` = corp / US address / verify credit; `Chinese phone/entity` = requires PRC-based identity; `high` = enterprise contract.
- **What it adds** — concrete capability delta over currently-wired vendors.
- **Verdict** — recommend / consider / skip.

---

## Tier 1 — different-capability gateways (adds something OR + Kilo + SF can't)

The strongest signal: these add speed tiers, fee-bypass, or exclusive-vendor coverage that the current wire cannot deliver.

| Vendor | Signup effort | What it adds | Verdict |
|---|---|---|---|
| **ModelScope** | trivial (token API — `ms-*` format) | **55-model Alibaba model hub inference.** Covers direct **ZhipuAI GLM** (`GLM-5.2` / `5.1` / `5` / `4.7-Flash` — Zhipu's own inference, likely cheapest route for GLM), **Shanghai AI Lab Intern-S series** (`Intern-S1` / `S1-mini` / `S2-Preview` — the InternLM3 successors), **PaddlePaddle ERNIE-4.5** (Baidu direct), **Xiaomi MiMo-V2-Flash**, **Tencent Hunyuan Hy3**, **XiYanSQL** (specialty SQL coder), plus overlap with 20 Qwen models, MiniMax M2.5/M2.7/M3, DeepSeek V3.2/V4-Flash/V4-Pro, Kimi K2.5. **Token operator has signed up 2026-07-09.** OpenAI-compatible endpoint `https://api-inference.modelscope.cn/v1`. Full wire-in TBD; env var `MODELSCOPE_API_KEY` in `.env`. | **KEY IN HAND — signed up.** Wire on par with SF |
| **Groq** | trivial | **LPU inference** — fastest tier for `llama-3.3-70b` / `mixtral-8x7b` (2-3× faster than any OR route). Latency-sensitive paths where speed dominates. | **Signup now.** Free tier + speed |
| **Cerebras** | trivial | **WSE inference** — peer of Groq, sometimes even faster; `llama-3.3-70b` at ~2000 tok/s | **Signup now.** Redundancy with Groq |
| **DeepInfra direct** | trivial | **Bypasses OR's 5.5% fee** on models where DeepInfra is already OR's cheapest provider (v4-flash, kimi-k2.7-code, deepseek-r1-0528, glm-5.2 — many more) | **Signup now.** Pure savings on models you route anyway |

## Tier 2 — cheaper alt routes for models you already have

Same capability, cheaper wire when the vendor undercuts OR's default routing.

| Vendor | Signup effort | What it adds | Verdict |
|---|---|---|---|
| **Novita direct** | trivial | Bypasses OR fee; often OR's cheapest endpoint for `deepseek-r1`, `glm-5.2` | Signup after Tier 1 |
| **Fireworks AI** | trivial | Solid alt for OSS models (Qwen, DeepSeek, Llama); competitive pricing | Signup after Tier 1 |
| **TogetherAI** | trivial | Similar to Fireworks; often cheapest for DeepSeek + Mixtral | Signup after Tier 1 |
| **Anyscale** | trivial | Llama-focused; cheap dedicated endpoints for Llama-3.3 | Skip unless you go all-in on Llama |

## Tier 3 — free-tier / experimentation

Low-commitment additions for dev workloads and A/B comparisons.

| Vendor | Signup effort | What it adds | Verdict |
|---|---|---|---|
| **Cloudflare Workers AI** | trivial | Very cheap edge inference; free tier includes daily neurons; 30+ models (Llama, Mistral, DeepSeek-R1) | **Signup now — free is free.** Good for burstable dev workloads |
| **HuggingFace Inference Providers** | trivial | Meta-gateway of gateways (Novita / Sambanova / Fireworks / Together / Cerebras all wired via HF); one key, many routes | Signup after Tier 1 if you'd rather have HF's aggregation layer than manage each provider directly |

## Tier 4 — direct-vendor for specific families

Bypass OR only when a model is exclusive to a vendor or the direct route is meaningfully cheaper.

| Vendor | Signup effort | What it adds | Verdict |
|---|---|---|---|
| **Zhipu (BigModel)** | Chinese phone/entity | **Direct GLM 5.2** — probably cheaper than OR route (`glm-5.2` output on Kilo is $1.32 vs $1.76 on OR; direct Zhipu likely undercuts both) | Skip unless you have Chinese phone — Kilo already wins on glm-5.2 |
| **Moonshot AI direct** | Chinese phone/entity | Direct Kimi K2 line access | Skip unless Chinese phone — Kilo covers Kimi |
| **Alibaba Model Studio (US console)** | mid — needs US-account Alibaba Cloud + credit card | Direct Qwen access; `qwen-mt-turbo` (already covered by DashScope) | Skip — DashScope already covers |
| **xAI direct (Grok)** | trivial | Grok models (grok-3, grok-4) direct; cheaper than OR for beta routes | **Consider** if you value Grok's specific behavior on real-time queries |
| **Mistral La Plateforme** | trivial | Direct Codestral + Ministral + Pixtral; sometimes cheaper than OR | Signup if you use Mistral models heavily; otherwise Tier 3 |
| **Cohere direct** | trivial | Command-R + Aya (multilingual); Cohere Embed | Signup if you want Aya for translation or Embed for classification |

## Tier 5 — enterprise / GPU marketplaces (not aggregators per se)

Different class — self-host / GPU rental rather than API-first inference.

| Vendor | Signup effort | What it adds | Verdict |
|---|---|---|---|
| **Hyperbolic** | mid | Cheap Llama routes + H100 rental (already on `CANDIDATE_SIGNUPS.md` watchlist) | Already flagged |
| **Baseten** | high | Enterprise model serving | Skip for solo-dev |
| **RunPod / Vast.ai / Lambda** | mid | GPU rental for self-host (partially scoped via GPU browser tab) | Already scoped |

---

## Recommended order of operations

Cost-adjusted-impact order for signup work:

1. **Signup + wire Groq + Cerebras (Tier 1)** — different capability tier (LPU/WSE speed). Follow the same 5-step pattern as the 2026-07-09 SiliconFlow wire-in:
   - Store `GROQ_API_KEY` / `CEREBRAS_API_KEY` in `.env` (gitignored)
   - Add row to `AI_VENDOR_ACCESS.md`
   - Update `.env.example` + `docs/CONFIGURATION.md`
   - Author `scrape_groq_catalog.py` / `scrape_cerebras_catalog.py` mirroring `scrape_siliconflow_catalog.py`
   - Wire step into `daily_refresh.sh` before `export_models_browser.py`
   - Add sidebar chip in `models_browser_template.html` (`via Groq` / `via Cerebras`)

2. **Signup + wire DeepInfra direct (Tier 1)** — pure savings on high-volume models. Same 5-step pattern.

3. **Signup + wire Cloudflare Workers AI (Tier 3)** — free tier is a no-brainer for burstable dev workloads.

4. **Signup + wire xAI direct (Tier 4)** — if Grok matters for the workload.

5. **Optionally: HuggingFace Inference Providers (Tier 3)** — meta-aggregator; one signup for many downstream providers, but adds a layer OR already provides.

**Skip:**
- Zhipu / Moonshot direct — Chinese phone requirement
- Volcano Ark (Doubao) — Chinese entity requirement
- Baseten — enterprise-sized effort

## Wiring pattern reference

The 2026-07-09 SiliconFlow wire-in (`commits 965e273a → ba674dc1` — chain: key → template → vendor row → seed → scraper → GUI chip) is the reference implementation for adding any of the above. Steps captured in the SiliconFlow `CHANGELOG.md` entry.

## Related docs

- `AI_VENDOR_ACCESS.md` — currently-wired vendors (single source of truth for `reachable_with_existing_keys` seeding)
- `CANDIDATE_SIGNUPS.md` — auto-generated per-model watchlist (rank_candidate_signups.py)
- `.windsurf/rules/ai/00-ai-model-selection.md` — selection workflow discipline
