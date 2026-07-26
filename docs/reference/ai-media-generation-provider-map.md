# AI Media-Generation Provider Reach Map

**Compiled:** 2026-07-25 · **Monetization pass added:** 2026-07-26 · **Scope:** every generative-media
provider (video / image / audio / 3D / editing / assembly / understanding), whether we can drive it in an
automated fashion (API / SDK / CLI / MCP) **without a human in a GUI**, exactly how we reach it — **and
the real-world businesses / revenue use cases each model powers.**

> Reach rule used throughout:
> **✅ callable now** = we hold a direct key OR it's on an aggregator we hold
> (WaveSpeed / fal / Replicate / ModelScope / SiliconFlow / DeepInfra / HF).
> **⚠️ catalogued, no key** = a row+price exists in `kilo_agents.db` but we can't actually call it.
> **❌ add-key** = not reachable at all without a new credential.
>
> Monetization lens: each **💰** cell lists proven ways people make money with that capability — the
> automatable, sellable service or product on top of the raw model. "Cost in, priced out" is the pattern:
> the model bills you cents; the finished deliverable sells for dollars.

---

## What we actually hold (the programmatic toolkit)

**Direct keys (media-relevant), confirmed in `.env`:** BFL, Stability, Recraft, ElevenLabs, OpenAI,
Gemini, Dashscope, Higgsfield — plus translation keys DeepL, Azure.
**Aggregators we hold:** fal, Replicate, WaveSpeed, ModelScope, SiliconFlow, DeepInfra, HuggingFace,
OpenRouter. **Stock:** Pexels, Pixabay, Unsplash.

Everything marked "✅ now" below routes through one of those. Everything "⚠️"/"❌" needs a new key.

---

## VIDEO — generation

| Provider | Unique lane | Reach | 💰 Real-world monetization |
|---|---|---|---|
| Seedance, Veo, Sora, Kling, Hailuo, Wan, PixVerse, Vidu, Grok, Luma, Pika | photoreal / all-purpose / keyframe / VFX-preset | **✅ now** — WaveSpeed + fal + Gemini/OpenAI keys | Faceless YouTube/TikTok/Reels channels (AdSense + sponsorships); **short-form video-ad creative for DTC/e-commerce brands** (per-ad or monthly retainer, $500–5k/mo/client); AI music/lyric videos for indie artists; real-estate listing tours; SaaS product-demo & explainer clips; stock-video packs sold on marketplaces |
| **Runway** | multi-motion brush, Act-Two mocap, Aleph reshoot | **⚠️ catalogued, no key** — NOT on any aggregator → **add RUNWAY key** | Premium ad **post-production** (Aleph "reshoot" — relight/fix/extend real footage, sold as a high-margin edit service); film & music-video VFX freelancing; virtual production for indie studios; performance-capture animation (Act-Two) without a mocap suit |
| Higgsfield DoP/Soul | camera-motion presets, identity | **✅ now** — Higgsfield CLI (validated 2026-07-26: **plus plan, ~110 credits — low, top up for volume**) + WaveSpeed DoP/Soul | **Product 360°-orbit videos for e-commerce** (the camera-rotation deliverable — sells per SKU); UGC-style ad packs at scale; personalized-creator content (Soul ID → one face across thousands of posts, sold to influencers/agencies) |
| **new:** Genmo, LTX (Lightricks), Moonvalley Marey, Haiper | open/real-time/licensed video | Genmo/LTX **✅ via Replicate/fal**; Moonvalley **❌ add-key** | Cheap high-volume social filler (open models keep COGS near-zero); Moonvalley's licensed-data output for **brand-safe** commercial spots where legal risk matters |

## VIDEO — talking avatars / digital humans

| Provider | Unique lane | Reach | 💰 Real-world monetization |
|---|---|---|---|
| **HeyGen** | studio avatars + 175-lang video translation | **⚠️ catalogued, no key → add HEYGEN key** | **Video-localization service** — dub a client's course/ad/YouTube into 30+ languages with lip-re-sync (one of the highest-margin AI services, $50–500 per video); AI spokesperson videos for course creators & corporate training; multilingual product marketing |
| **new:** Tavus | **developer-first conversational/personalized video API** | **❌ add-key** — high value, no path | **Personalized-video-at-scale SaaS** (real-estate, insurance, sales outreach — "Hi {name}" video to each lead); interactive AI-avatar agents embedded in apps (onboarding, support), sold B2B per-seat or per-minute |
| **new:** Synthesia, D-ID, Hedra, Argil, Captions, Creatify, Arcads | presenter / photo-talking-head / UGC-actor ads | **❌ add-key** each; Higgsfield Marketing Studio is a partial substitute **✅** | **UGC-influencer ad factories** (Arcads/Creatify style — AI "actors" reading ad scripts, sold to brands as ad-creative subscriptions); training-video studios (Synthesia); talking-head content for faceless creators; personalized birthday/greeting video products (D-ID) |

## VIDEO — lip-sync, mocap, assembly, understanding

| Provider | Unique lane | Reach | 💰 Real-world monetization |
|---|---|---|---|
| **Sync.so** | best dedicated lip-sync/dubbing | **✅ now — it's in WaveSpeed as `sync/*`** | Podcast/course/ad **dubbing service** (translate + perfect lip-sync); fix lip-sync on any translated footage as an add-on to a localization business |
| **Viggle, Move AI, Wonder Dynamics** | markerless mocap / character motion | Viggle **⚠️/❌**; Move AI, Wonder Dynamics **❌ add-key** | Viral meme/character-animation content (Viggle → TikTok engagement → sponsorship); indie-game & VTuber **character animation service** (Move AI); CG-character-into-live-footage for ad/film studios (Wonder Dynamics) |
| **Creatomate, Shotstack, JSON2Video** | **programmatic video/image ASSEMBLY** (REST) | **❌ add-key** — useful glue you don't have | **Bulk personalized-video-ad SaaS** — feed a product/CSV feed, auto-render thousands of tailored video ads or social posts (agencies pay for this; it's the "1000 ads overnight" product); automated daily social content pipelines |
| **TwelveLabs** | video understanding/search/scene-indexing | **❌ add-key** (Higgsfield Virality Predictor is a narrow substitute **✅**) | Content-moderation SaaS; searchable video-library infrastructure sold to media/e-learning; **ad-creative analytics** (which second hooks, why) sold to marketers |

## IMAGE — generation + editing

| Provider | Unique lane | Reach | 💰 Real-world monetization |
|---|---|---|---|
| Nano Banana, Seedream, GPT Image 2, Grok, MAI-Image, Flux, Stability | photoreal / character / general | **✅ now** — Gemini/OpenAI/BFL/Stability keys + fal + WaveSpeed | **AI headshots/portraits** ($30–50/person, near-100% margin — huge market); **print-on-demand designs** (Etsy/Redbubble t-shirts, posters, wall art); social-media content & thumbnail services; book covers & album art for indie creators; ad-creative generation for agencies; stock-image packs |
| **Recraft** | vector/SVG + brand palette | **⚠️ direct key has 0 credits** (validated 2026-07-26: `/users/me`→`credits:0`) — reach via **fal + Replicate ✅**, or top up `recraft.ai` | **Logo & brand-kit generation service**; icon/illustration packs sold on design marketplaces (Creative Market, UI8); merch/print design (true vector = clean at any size, sells to print shops) |
| **Ideogram** | best on-image text | **✅ now — via fal + Replicate** | **Social graphics with text as a service** (quote cards, promo banners, sale creatives); ad headlines baked into images; poster/flyer design for local businesses & events; typography meme accounts |
| BFL **Flux Kontext** | context-aware editing, Fill/Redux/Canny/Depth | **✅ now** — BFL key + fal | **Virtual staging** for real-estate photos (empty room → furnished, $10–30/photo); product restyling & seasonal variants; object removal / photo-cleanup service; controllable brand-consistent asset pipelines |
| **new:** Reve, Freepik Mystic | new high-quality image models | Freepik **⚠️/❌**; Reve **❌ add-key** | Same plays as the general image lane; Freepik's ecosystem is a distribution channel (sell templates/assets into their marketplace) |
| **Bria AI** | **commercially-safe (licensed-data) editing API** | **✅ now — via fal** (validated 2026-07-26: `bria/background/remove\|replace`, `eraser`, `expand`, `embed-product`, `fibo-edit/*`; ~$0.018–0.023/op) | **Enterprise/agency image gen with legal indemnity** — brands & publishers pay a premium for copyright-safe, IP-clean assets they can use in paid campaigns without exposure |

## IMAGE — product-photo / background (the business-critical lane)

| Provider | Unique lane | Reach | 💰 Real-world monetization |
|---|---|---|---|
| **Photoroom** | **THE product-photography API** — bg removal ($0.02/img), AI backgrounds/shadows/relighting, catalog-scale; REST **+ MCP**. Decathlon: 35k imgs in 3mo, −99.8% edit time | **❌ add-key** — strongest add; = `iterative_image_editor` | **Automated product-photo service for marketplace sellers & dropshippers** (per-image or subscription — this IS the iterative-image-editor business); bulk catalog processing for retailers (charge per-SKU); a consumer background-remover app (subscription); Amazon/Etsy listing-image optimization service |
| **remove.bg / ClipDrop** | pure bg removal / SD editing | **❌ add-key** (Photoroom beats remove.bg ~30%) | Same as above at a simpler tier — cutout-as-a-service, bulk white-background listing images for e-commerce |
| **Higgsfield product-photoshoot** | 10 product templates on GPT Image 2 | **✅ now** — Higgsfield CLI | Lifestyle/hero/ad-creative product shots, virtual try-on, Pinterest-pin packs — sold to DTC brands & agencies as a "brand visual pack" |

## AUDIO — voice, music, STT, dubbing

| Provider | Unique lane | Reach | 💰 Real-world monetization |
|---|---|---|---|
| **ElevenLabs** | voice clone / TTS / dubbing / music | **✅ now — direct key** | **Audiobook narration** for self-publishers (Audible/ACX — a full book for the cost of a coffee); AI voiceover for YouTube/ads; podcast production & AI ad-reads; character voices for games; **creator voice-cloning** (their voice → bulk content, licensed back to them); accessibility read-aloud apps |
| TTS: OpenAI, Gemini, Azure, Coqui, Sesame, Kokoro, Canopy, Zyphra | broad TTS | **✅ now** — keys + aggregators | High-volume/low-cost narration where ElevenLabs is overkill; open models (Kokoro/Coqui) keep COGS ~0 for a freemium read-aloud or TTS-widget product |
| **Cartesia, PlayHT** | lowest-latency realtime voice | **⚠️ catalogued, no key** — ElevenLabs covers; add for realtime | **AI phone agents / voice bots for SMBs** — receptionist, booking, lead-qualification, support (high-value B2B, $200–2k/mo/business); realtime voice assistants embedded in apps |
| **STT: Whisper (OpenAI)** + Soniox, Speechmatics, Azure, Qwen | speech→text | **✅ now** — OpenAI key + aggregators | **Transcription service** (meetings, podcasts, legal/medical — per-minute); auto-subtitle/caption generation for creators; meeting-notes SaaS; call-center QA & analytics |
| **Deepgram, AssemblyAI** | best-in-class STT | **⚠️ catalogued, no key → add-key** if needed | Same, at higher accuracy/speed tiers where transcription quality is the product (medical, legal, compliance) |
| **Suno / Udio** | full songs w/ vocals+lyrics | **❌ no official API** — only the fragile **Kie.ai** bridge | **Personalized-song products** (birthday/wedding/anniversary songs — $10–30 each, viral gifting); custom jingles for SMBs; original tracks for video/game creators — *but automation risk means don't build a core business on the unofficial bridge* |
| **new: Mubert, Beatoven, Loudly, Riffusion** | **royalty-free music WITH real APIs** | Riffusion **✅ via Replicate**; Mubert/Beatoven/Loudly **❌ add-key** | **Royalty-free background-music licensing** for the video/podcast lane (sell/bundle with your video services — no copyright strikes); streaming ambient/focus-music apps (Mubert-style subscription); auto-scored soundtracks for the assembly pipeline |

## 3D

| Provider | Reach | 💰 Real-world monetization |
|---|---|---|
| Meshy, Tripo, Hunyuan3D | **✅ now — via Higgsfield** | **Game-asset generation** for indie devs (sell packs on Unity/Unreal marketplaces, Sketchfab); **3D product models for AR/e-commerce** ("view in your room" — retailers pay per-SKU); 3D-printing model marketplace (Cults3D, Thingiverse Plus); metaverse/VR asset creation |
| **Rodin (Hyper3D)** — top film-grade fidelity | **❌ add-key** | Hero/character assets for film, archviz, high-end game studios — premium per-asset pricing where fidelity is the product |
| **new:** Scenario, Kaedim, CSM, Sloyd (game-asset 3D) | **❌ add-key** each | Studio-style **game-art pipelines** (Scenario: train on a studio's style, sell consistent asset generation); 2D-concept→3D services (Kaedim) sold to game teams |

## Enhancement / other lanes we own

- **Upscale:** Topaz **✅ (WaveSpeed)**; Clarity **✅ via Replicate**; Magnific **❌ add-key**.
  **💰** Photo-**restoration** service (old/blurry photos → HD, huge with genealogy/nostalgia buyers,
  $5–20/photo); print-prep upscaling for large-format & canvas printing; video remastering (SD → 4K)
  for archives & creators.
- **OCR:** Mistral OCR, AWS Textract, Google, Azure, LlamaIndex — **✅ catalogued**.
  **💰** Document-digitization service; **invoice/receipt-processing SaaS** (accounting automation);
  data-extraction pipelines sold to SMBs; searchable-archive products.
- **Translation:** **DeepL ✅ (direct key)**, Azure ✅, Google, Amazon, Qwen.
  **💰** Content-localization service (feeds the video-dubbing & multilingual-SEO plays); multilingual
  e-commerce listings at scale.
- **Rerank/Embedding:** Cohere, Nvidia, BAAI, OpenAI — **✅**.
  **💰** Not sold directly — the **infrastructure** under paid products: RAG search, recommendation,
  semantic dedup, the retrieval layer that makes a "smart" app worth a subscription.

---

## Highest-ROI business plays (where the money actually is, ranked)

The pattern that wins: **automate a deliverable that currently costs a human hours, price it per-unit or
per-seat, keep model COGS in the cents.** Ranked by margin × market size × how close it is to what we
already reach:

1. **Automated product photography (Photoroom + Nano Banana + Higgsfield product-photoshoot)** — the
   `iterative_image_editor` business. Marketplace sellers pay per-image or subscribe; COGS ~$0.02–0.08,
   sells for $1–10/image or $20–200/mo. **Nearest to shipping; add Photoroom.**
2. **Video localization / dubbing (HeyGen + Sync.so + DeepL + ElevenLabs)** — dub one video into 30
   languages; $50–500/video, minutes of compute. Highest-margin video service. **Add HeyGen.**
3. **Bulk personalized video-ad SaaS (Creatomate/Shotstack + Seedance/Kling + the avatar lane)** —
   "1000 tailored ads overnight" for agencies/DTC. **Add an assembly key.**
4. **AI headshots & portraits (Flux / Nano Banana / GPT Image)** — $30–50/person, near-100% margin,
   already fully reachable. **Zero new keys — could ship today.**
5. **AI phone agents for SMBs (Cartesia/PlayHT + Whisper + an LLM)** — $200–2k/mo/business, sticky B2B.
6. **Audiobook / voiceover production (ElevenLabs)** — self-publisher & creator market, already reachable.
7. **Personalized songs (Suno via Kie.ai)** — viral gifting, but built on an unofficial bridge → treat as
   a side experiment, not a core product.
8. **3D product/AR assets (Meshy/Tripo)** & **photo restoration (Topaz)** — steady niche demand, reachable now.

**Ship-today set (zero new keys):** AI headshots, product photoshoots (Higgsfield), voiceover/audiobooks
(ElevenLabs), transcription/captioning (Whisper), social graphics-with-text (Ideogram), logo/vector packs
(Recraft), virtual staging (Flux Kontext), 3D AR assets (Meshy/Tripo), photo restoration (Topaz).

---

## Applied: the two video-creation pipelines (cost-optimal tool stack)

The single most important lesson from building `video-factory`: **automated video is assembly, not
generation.** You never pay a per-second API to hallucinate frames (Seedance/Veo/Runway — great, but
100–1000× the cost). You composite cheap parts with FFmpeg, and only rent a GPU for the one thing that
needs it — a face. Two pipelines, switched by the profile's `avatar.mode`, sharing ~80% of the machine
(script → TTS → captions → metadata → publish) and diverging only at the visual render. Per-minute costs
are live-researched (2026-07-26); GPU rates from RunPod/Vast.

### Pipeline 1 — Faceless (CPU, no GPU, `avatar.mode: none`)

**Narrative.** A script (Claude via OpenRouter) becomes narration audio, laid over **stock B-roll**
keyword-matched to each scene, with lower-thirds / PMID citations / title-cards layered per
`scene.layout`, and captions burned in — all muxed by **FFmpeg templated filter graphs** (one graph per
aspect-ratio × layout, picked by the profile's `template_id`). No neural rendering happens, so there is
**no GPU and ~$0 render cost**. A `broll_history` table enforces 90-day clip uniqueness so the same stock
footage never visibly repeats across videos.

**Selected tools:**

| Stage | Tool | Reach | $/min |
|---|---|---|--:|
| Script | **Claude** via OpenRouter | ✅ OpenRouter key | ~$0.01/video |
| Narration (TTS) | **ElevenLabs** (premium) · **Kokoro** self-host Apache-2.0 (cheap, CPU-capable) · **Chatterbox** MIT (cloned voice) | ✅ ElevenLabs key / self-host | ElevenLabs ~$0.09–0.16 · Kokoro ~$0.001 |
| Visual (B-roll) | **Pexels + Pixabay** stock (keyword-matched) · gap-fill: self-host **LTX** for scenes stock can't cover | ✅ stock keys / own GPU | stock $0 · generative fill ~$0.10–0.50 |
| Overlays | **FFmpeg** filter graphs — lower-thirds, PMID citation chips, title-cards, per `scene.layout` × `template_id` | CPU (VPS) | ~$0 |
| Captions | **Whisper** self-hosted (burned-in) | ✅ self-host | ~$0.001 |
| Composite/encode | **FFmpeg** (NOT MoviePy) | CPU (VPS) | ~$0 |
| **≈ per finished minute** | | | **~$0.01–0.02 (self-host) → ~$0.15–0.60 (premium)** |

### Pipeline 2 — Avatar / talking-head (GPU, `avatar.mode: corner_bubble | full_frame`)

**Narrative.** Everything from Pipeline 1, plus an **audio-driven talking head**: a source portrait
animated to the exact narration audio, shown either as a corner bubble over the same B-roll or full-frame.
The face is the *only* thing that touches a GPU — B-roll fetch, overlays, captions and the final composite
stay on FFmpeg/CPU. Because the VPS has no GPU, the animation runs on an **external rented GPU** and the
orchestrator dispatches render jobs **via provider API and never SSHs in** (the two-faced pattern mandated
by `core/76-gpu-workers.md`). Serverless scale-to-zero means you pay only for the ~30–900 GPU-seconds a
video actually needs — cents each, not the $0.50–2.00/min a commercial suite (HeyGen) charges for the same
talking head.

**Selected tools:**

| Stage | Tool | Reach | $/min |
|---|---|---|--:|
| *(shared)* Script / TTS / B-roll / overlays / captions / composite | *(as Pipeline 1)* | ✅ | ~$0.01–0.15 |
| Face — **default** | **MuseTalk** — lip-sync onto a pre-rendered idle-avatar loop · ★★★★ · real-time | ✅ self-host (verify license) | **$0.01–0.02** |
| Face — corner-bubble | **LivePortrait / SadTalker** — image→head, expression + pose · ★★★★ | ✅ self-host | $0.02–0.06 |
| Face — hero / still-photo→head | **LatentSync 1.6 / Hallo2** — diffusion, top-fidelity · ★★★★★ (L40S) | ✅ self-host | $0.15–0.45 |
| Voice (optional self-host) | **Kokoro / Chatterbox** on the same warm GPU (co-located with the face model → ~$0) | ✅ self-host | ~$0 |
| GPU rental | **RunPod 4090 serverless** ($1.10/hr, scale-to-zero) primary · **Vast 4090/L40S spot** (~$0.24–0.47/hr) for batch · Modal DX · **Hyperbolic $1.49/hr** & **Novita $1.79/hr** H100 for LLM-heavy side-work | ✅ all 5 keyed | — |
| **≈ per finished minute** | | | **default ~$0.03–0.05 → premium ~$0.40–1.00** (vs HeyGen $0.50–2.00 for the face alone) |

**The elegant part:** same orchestrator, same script/voice/captions/publish — the profile flips one field
(`avatar.mode`) and you get a different render backend. One codebase, config-switched pipelines. The
default avatar architecture — pre-render one looping idle clip per profile, then MuseTalk lip-syncs each
narration onto it — delivers a HeyGen-class presenter at **~1/25th the cost**.

**⚠️ License note:** self-hosted models may be trialled freely; before a **monetized** channel ships on
one, confirm a commercial license. Non-commercial traps (test-only): TTS **XTTS-v2 (CPML), F5-TTS
(CC-BY-NC), Fish (CC-BY-NC-SA)**; several avatar models are research/non-commercial — verify each at
adoption. Commercial-safe voice defaults: **Kokoro (Apache-2.0)**, **Chatterbox (MIT)**.

_(Full design + tickets: `video-factory-vision-intake.md` §10–§11.)_

---

## The complete verdict

**Genuinely un-automatable (no API exists):** **Midjourney** (Discord/GUI only), **Suno/Udio**
(no official API — Kie.ai bridge only). Everything else in this space *has* an API.

**Catalogued but we can't call it (no key, no aggregator path) — the real gaps, ranked by value:**

1. **Photoroom** — automated product photography, the actual business. *Biggest win.*
2. **Runway** — the entire creative-control/mocap video lane; irreplaceable.
3. **HeyGen or Tavus** — talking-avatar / conversational-video (powers the #2 monetization play).
4. **Creatomate/Shotstack** — programmatic assembly to turn generated clips into finished ads.
5. **Mubert/Beatoven** — royalty-free music with a real API (clean alternative to the Suno dead-end).
6. Lower priority: Deepgram/AssemblyAI (STT), Cartesia (realtime voice), Rodin (hero 3D), Magnific (upscale).
7. **Top up existing keys, not new ones:** **Recraft** (direct key valid, $0 credits → fund `recraft.ai`
   *or* just use fal/Replicate) and **Higgsfield** (plus plan, only ~110 credits → top up for real volume).

_(~~Bria~~ removed from gaps — validated reachable via fal, 2026-07-26.)_

**Reachable right now with zero new keys** (via the keys + 7 aggregators we already hold): essentially
the entire video-gen, image-gen/editing, TTS, STT, translation, OCR, rerank, embedding, Topaz upscale,
Sync.so lip-sync, and Meshy/Tripo/Hunyuan 3D lanes.

---

## Source notes

- Provider API availability live-verified 2026-07-25 (Runway `api.dev.runwayml.com/v1` production REST;
  Pika direct API; Luma `lumaai` SDK; Kling `api.klingai.com`; Suno/Udio confirmed **no** official API;
  Meshy/Tripo/Rodin/BFL official APIs; Photoroom REST+MCP `photoroom.com/api`; Bria licensed editing;
  Creatomate assembly REST; Midjourney GUI/Discord-only).
- Our held keys + catalogued rows read from `/opt/fabrik/.env`,
  `/opt/iterative_image_editor/.env`, and `scripts/kilo-benchmarks/kilo_agents.db` (service_type
  breakdown: image_gen 50, video_gen 28, tts 22, stt 18, embedding 20, translation 8, ocr 5, rerank 4,
  music_gen 4) + `specialty_pricing.py`.
- "In our DB" means a catalogued row (for the bake-off browser / cost comparison), which is distinct
  from a callable integration — the reach column reflects callability, not mere cataloguing.

### Validation log — 2026-07-26 (three externally-suggested corrections, verified against ground truth)

- **Recraft ✅→⚠️ — CONFIRMED.** `GET external.api.recraft.ai/v1/users/me` → `{"credits":0,"email":
  "ob@ocoron.com"}`. Direct key valid (HTTP 200) but zero credits. Lane still ✅ via fal/Replicate.
- **Bria ❌→✅ — CONFIRMED.** Our fal catalog carries the full Bria suite (`bria/background/*`,
  `eraser`, `expand`, `embed-product`, `fibo-edit/*`); reachable on the fal key, no new credential.
- **Higgsfield "✅ CLI→⚠️ MCP-only-on-trial" — REJECTED (correction was wrong).** `higgsfield account
  status` → **"plus plan, 110 credits"**; CLI generation functional (`generate cost nano_banana_2`
  → "2 credits"); DoP/Soul also on WaveSpeed. Not MCP-only, not trial-blocked. Kept ✅, noted the low
  ~110-credit balance as the only real caveat.
- Monetization use cases are illustrative of established markets (per-image editing, video localization,
  AI headshots, personalized-video SaaS, audiobook narration, transcription, royalty-free music, 3D/AR
  assets), not revenue guarantees; pricing figures are indicative market ranges as of mid-2026.
