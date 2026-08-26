# NVIDIA Build — free inference endpoints (build.nvidia.com)

**Last Updated:** 2026-08-26

Owned external service: NVIDIA Build's free, OpenAI-compatible inference endpoints. One key,
zero cost, rate-limited per key (limits not yet probed — observe `429`s in practice).

| Fact | Value |
|---|---|
| Base URL | `https://integrate.api.nvidia.com/v1` (OpenAI-compatible: `/models`, `/chat/completions`) |
| Key env var | `NVIDIA_API_KEY` (hub `.env`; placeholder in `.env.example`) |
| Key name in the NVIDIA console | `NVIDIABuild-Autogen-17` |
| Cost | $0 — free endpoints (the whole point; no metered tier is wired anywhere) |
| Proven | 2026-08-26: `/v1/models` → HTTP 200, **83 model ids**; live completion on `nvidia/nemotron-3-nano-30b-a3b` returned the probe string (118 tokens) |

Policy fit: the operational LLM stack is Claude Max OAuth + OpenRouter (Kilo/Cascade retired
2026-07-19; direct APIs only for models not on OpenRouter). A **free** endpoint doesn't breach the
no-metered-direct-API intent, and several of these models are not on OpenRouter at all — that gap
is this key's value.

## Catalog (grounded: the key's live `/v1/models` response, 2026-08-26)

Only the categories below matter for fabrik work; the full 83-id list is reproducible with
`curl -H "Authorization: Bearer $NVIDIA_API_KEY" https://integrate.api.nvidia.com/v1/models`.

**Text / agentic / coding LLMs (subagent-shaped):**

| Model id | Notes (vendor blurb) |
|---|---|
| `deepseek-ai/deepseek-v4-flash-0731` | 284B MoE (13B active), long-context, coding/chat/agentic |
| `nvidia/nemotron-3-ultra-550b-a55b` | hybrid Mamba-Transformer MoE, 1M context, agentic reasoning/coding/tool-calling — the flagship |
| `nvidia/nemotron-3-super-120b-a12b` | same family, mid tier |
| `nvidia/nemotron-3-nano-30b-a3b` (+ alias-ish `nvidia/nemotron-nano-3-30b-a3b`) | 1M-context MoE nano — the probe model |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | fastest 30B A3B, specialized agentic tasks |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | omni-modal (image/video/speech/text) reasoning |
| `moonshotai/kimi-k3`, `moonshotai/kimi-k2.6` | in the API listing though absent from the UI page dump |
| `openai/gpt-oss-120b`, `openai/gpt-oss-20b` | MoE reasoning, text-only |
| `minimaxai/minimax-m3` | multimodal MoE, coding + tool-calling |
| `stepfun-ai/step-3.7-flash` | sparse MoE multimodal, enterprise/agentic/coding |
| `poolside/laguna-xs-2.1` | 33B MoE, long-horizon agentic coding/terminal |
| `google/gemma-4-31b-it` | dense 31B frontier reasoning |
| `google/diffusiongemma-26b-a4b-it` | diffusion LLM (parallel token generation) — exotic, text-out |
| `meta/muse-glimmer-30b` | multimodal reasoning, native tool-calling, separate reasoning output |
| `mistralai/mistral-nemotron` | agentic, coding, function calling |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1`, `-70b-instruct`, `-51b-instruct` | previous-gen nemotron line |

**Vision-language (chat-capable, image-in):** `meta/llama-3.2-90b-vision-instruct`,
`meta/llama-3.2-11b-vision-instruct`, `microsoft/phi-3-vision-128k-instruct`, `nvidia/vila`,
`nvidia/neva-22b`, `nvidia/cosmos-reason2-8b` (physical-world video reasoning).

**Embeddings / retrieval:** `nvidia/nemotron-3-embed-1b`, `nvidia/embed-qa-4`,
`nvidia/llama-3.2-nv-embedqa-1b-v1`, `nvidia/nv-embedqa-mistral-7b-v2`,
`nvidia/llama-nemotron-embed-vl-1b-v2`, `nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1`,
`snowflake/arctic-embed-l`. (UI also lists deprecated `nv-embedcode-7b-v1` / `nv-embed-v1`.)

**Safety / moderation classifiers (not generators):** `nvidia/nemotron-3.5-content-safety`,
`nvidia/llama-3.1-nemotron-safety-guard-8b-v3`, `nvidia/llama-3.1-nemoguard-8b-content-safety`,
`nvidia/llama-3.1-nemoguard-8b-topic-control`, `meta/llama-guard-4-12b`,
`nvidia/nemotron-4-340b-reward` (reward model).

**Translation:** `nvidia/riva-translate-4b-instruct{,-v1.1,-v2}` (37 languages in v2 — includes
the en↔tr pair the i18n mandate needs; few-shot capable).

**Speech/audio, video/world, autonomous-driving, niche VLM:** TTS (`magpie-tts-zeroshot`,
voicechat), audio cleanup (noise removal, Studio Voice), Cosmos world models, synthetic-video
detector, StreamPETR/SparseDrive/BEVFormer, quantum-calibration VLMs (`ising-calibration-*`),
`nemotron-parse`, `deplot`, `kosmos-2`, `paligemma`, `fuyu-8b` — none are subagent-shaped; listed
so nobody re-derives that.

**UI-catalog entries NOT in this key's `/v1/models` listing** (verify before use — the listing is
the invocable truth): `nvidia/nemotron-nano-12b-v2-vl`, `nvidia/llama-3.3-nemotron-super-49b-v1.5`,
`nvidia/nvidia-nemotron-nano-9b-v2`, `nvidia/cosmos3-nano*`, `nvidia/riva` voice items with GUI-only
cards.

## Can the subagents pool (`libs/subagents`) use these?

**Today: not through `fanout`/`pick_models` — the pool is OpenRouter-only by construction.**
`_transport.py::_resolve_client` builds the client from `OPENROUTER_API_KEY` with the OpenRouter
base URL as the constructor default (`_client.py:298`), and nothing in the dispatch API
(`AgentSpec`, `run_agents`, `fanout`) exposes `base_url`/`api_key` — the injectable-client seam
exists only for tests. The flywheel ranking (`pick_models`) and pricing also key on OpenRouter ids.

**What works right now, no code change:**

- **Direct calls** from any script/grader/one-off: OpenAI-compatible `POST /chat/completions` with
  `NVIDIA_API_KEY` — proven live (see probe above). Good for benchmark harnesses, graders, and
  bulk offline passes where flywheel recording doesn't apply.
- **The overlap set via OpenRouter (metered):** several catalog models are also on OpenRouter
  (`deepseek-v4-flash`, `minimax-m3`, `gpt-oss-120b`, `kimi-k3`, nemotron line) — the pool already
  uses some of them from the rankings. The NVIDIA key adds a $0 path to the same weights, not new
  pool capability.

**To wire the free endpoint INTO the pool** (not done — `libs/subagents` had sibling WIP in flight
when this doc landed, and it's a design decision): the minimal seam is `_resolve_client` learning
an env-driven provider override (e.g. `SUBAGENTS_BASE_URL`/`SUBAGENTS_API_KEY`) or a per-spec
`provider:` field mapping to (base_url, key env). Costs to weigh: free-tier RPM under a 10-way
fan-out, no OpenRouter health-aware rerouting (the zero-output-cap recovery leans on it), and
flywheel rows whose model ids no longer match OpenRouter pricing (cost would need to record as $0).

**Which models fit which pool task types, once reachable** (or today via the OpenRouter overlap):

| Pool task type | Fit from this catalog |
|---|---|
| `code` / implementers | `deepseek-v4-flash-0731`, `laguna-xs-2.1`, `nemotron-3-ultra-550b-a55b`, `gpt-oss-120b`, `step-3.7-flash` |
| `review` / finders | `nemotron-3-ultra-550b-a55b`, `kimi-k3`, `minimax-m3`, `gemma-4-31b-it`, `gpt-oss-120b` |
| `research` / grounders (tools) | tool-callers: `nemotron-3-*` family, `mistral-nemotron`, `muse-glimmer-30b`, `kimi-k3`, `minimax-m3` |
| `docs` / reconcilers | any mid tier: `nemotron-3-super-120b-a12b`, `gemma-4-31b-it`, `gpt-oss-20b` |
| cheap bulk (read-only single-shot) | `nemotron-3-nano-30b-a3b`, `nemotron-3.5-lightning-30b-a3b`, `gpt-oss-20b` |
| NOT pool material | embeddings, safety classifiers, reward, translation, TTS/audio, video/world, AV stacks, niche VLMs |

Read-only single-shot fan-outs (`tools_enabled=False`, the breadth default) accept any chat model;
write-mode needs function calling (the tool-caller row).

## Related

- Pool selection/rankings: `libs/subagents/select.py` + `docs/reference/MD/TASK_SUBAGENT_SELECTION.md`
- Media-side provider map (different concern): `docs/reference/ai-media-generation-provider-map.md`
