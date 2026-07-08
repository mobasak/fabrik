# RunPod Serverless — Hugging Face deployable models

**Last verified:** 2026-06-16 (RunPod's "Deploy LLM from Hugging Face" picker, vLLM-backed endpoint)
**Source:** RunPod console at `console.runpod.io/serverless/new` → "Deploy LLM from Hugging Face"
**Why this exists:** when picking the template for the [`fabrik gpu rent`](../development/plans/archived/2026-06-17-gpu-rent-and-serverless-shipped/2026-06-16-fabrik-gpu-rent.md) plan's `RUNPOD_SERVERLESS_TEMPLATE_ID`, you choose the underlying model. Re-verify before relying on any specific row — RunPod adds/removes models without notice.

---

## Picks for the gpu-rent Phase 1 smoke test (G-LIVE-1)

Smallest cold-start = cheapest gate. Prefer the **bold** row first.

| Model | Params | Cold-start budget | Why |
|---|---|---|---|
| **`huggingfacetb/smollm2-135m-instruct`** | **135M** | **~1–2 s on L40S** | **Smallest viable instruct LLM in the list. Default for smoke tests.** |
| `huggingfacetb/smollm2-135m` | 135M | ~1–2 s | Base (no instruct tuning); use if you want raw completion behavior |
| `huggingfacetb/smollm2-360m-instruct` | 360M | ~2–3 s | Slightly more capable than 135M |
| `qwen/qwen2.5-0.5b-instruct` | 500M | ~3 s | First "useful" tier — recognizable Qwen family |
| `qwen/qwen2.5-0.5b` | 500M | ~3 s | Base version of the above |
| `meta-llama/llama-3.2-1b-instruct` | 1B | ~5 s | Recognizable Llama at smallest size |
| `tinyllama/tinyllama-1.1b-chat-v1.0` | 1.1B | ~5 s | Chat-tuned tiny Llama variant |
| `qwen/qwen2.5-1.5b-instruct` | 1.5B | ~6 s | Useful in real chat workloads |

**Recommendation for G-LIVE-1**: `huggingfacetb/smollm2-135m-instruct`. Smallest cold-start, lowest cost, proves the round-trip works without burning budget.

---

## Full inventory (verified 2026-06-16)

Grouped by family. **vLLM-served** under the hood via RunPod's HF deployment flow.

### Qwen (Alibaba)

| Model | Params | Notes |
|---|---|---|
| `qwen/qwen2.5-0.5b` | 500M | Base |
| `qwen/qwen2.5-0.5b-instruct` | 500M | Instruct |
| `qwen/qwen2.5-1.5b-instruct` | 1.5B | Instruct |
| `qwen/qwen2.5-3b` | 3B | Base |
| `qwen/qwen2.5-3b-instruct` | 3B | Instruct |
| `qwen/qwen2.5-7b` | 7B | Base |
| `qwen/qwen2.5-7b-instruct` | 7B | Instruct |
| `qwen/qwen2.5-7b-instruct-1m` | 7B | 1M context window |
| `qwen/qwen2.5-14b` | 14B | Base |
| `qwen/qwen2.5-14b-instruct` | 14B | Instruct |
| `qwen/qwen2-7b-instruct` | 7B | Qwen2 (older gen) |
| `qwen/qwen2.5-math-1.5b` | 1.5B | Math-specialized |
| `qwen/qwen2.5-math-7b` | 7B | Math-specialized |
| `qwen/qwq-32b-awq` | 32B | QwQ reasoning, AWQ-quantized |

### Llama (Meta)

| Model | Params | Notes |
|---|---|---|
| `meta-llama/llama-3.2-1b-instruct` | 1B | Smallest Llama 3.2 |
| `meta-llama/llama-3.2-3b` | 3B | Base |
| `meta-llama/llama-3.1-8b-instruct` | 8B | Llama 3.1 instruct |
| `meta-llama/meta-llama-3-8b` | 8B | Llama 3 base |
| `meta-llama/meta-llama-3-8b-instruct` | 8B | Llama 3 instruct |
| `meta-llama/llama-2-7b-hf` | 7B | Legacy Llama 2 |
| `meta-llama/llama-guard-3-8b` | 8B | Safety/moderation classifier |
| `unsloth/meta-llama-3.1-8b-instruct` | 8B | Unsloth-optimized Llama 3.1 |
| `nousresearch/hermes-3-llama-3.1-8b` | 8B | Hermes-3 finetune |
| `nousresearch/hermes-3-llama-3.2-3b` | 3B | Hermes-3 finetune (smaller) |
| `orenguteng/llama-3.1-8b-lexi-uncensored-v2` | 8B | Uncensored finetune |
| `dphn/dolphin-2.9-llama3-8b` | 8B | Dolphin finetune |
| `mlp-ktlim/llama-3-korean-bllossom-8b` | 8B | Korean-tuned Llama 3 |
| `bllossom/llama-3.2-korean-bllossom-3b` | 3B | Korean-tuned Llama 3.2 |
| `s4nfs/neeto-1.0-8b` | 8B | Llama-derived finetune |
| `sao10k/l3-8b-stheno-v3.2` | 8B | Roleplay finetune |
| `salesforce/llama-xlam-2-8b-fc-r` | 8B | Salesforce xLAM (function-calling) |

### Mistral

| Model | Params | Notes |
|---|---|---|
| `mistralai/mistral-7b-v0.1` | 7B | Base v0.1 |
| `mistralai/mistral-7b-instruct-v0.1` | 7B | Instruct v0.1 |
| `mistralai/mistral-7b-instruct-v0.2` | 7B | Instruct v0.2 (current default) |
| `mistralai/mistral-7b-v0.3` | 7B | Base v0.3 |
| `mistralai/mistral-small-24b-instruct-2501` | 24B | Mistral Small (2501 release) |
| `mistralai/mistral-small-24b-base-2501` | 24B | Mistral Small base |
| `mistralai/codestral-22b-v0.1` | 22B | Code-specialized |
| `teknium/openhermes-2.5-mistral-7b` | 7B | OpenHermes finetune |
| `huggingfaceh4/zephyr-7b-beta` | 7B | Zephyr (Mistral-based) |
| `dphn/dolphin-mistral-24b-venice-edition` | 24B | Dolphin Mistral finetune |
| `latitudegames/wayfarer-2-12b` | 12B | Mistral-based roleplay |

### Microsoft Phi

| Model | Params | Notes |
|---|---|---|
| `microsoft/phi-2` | 2.7B | Phi-2 (older) |
| `microsoft/phi-3-mini-4k-instruct` | 3.8B | Phi-3 mini, 4K context |
| `microsoft/phi-3-mini-128k-instruct` | 3.8B | Phi-3 mini, 128K context |
| `microsoft/phi-3.5-mini-instruct` | 3.8B | Phi-3.5 mini |
| `microsoft/phi-4` | 14B | Phi-4 (current flagship) |
| `microsoft/phi-4-reasoning-plus` | 14B | Phi-4 reasoning variant |
| `microsoft/dialogpt-medium` | ~355M | Legacy conversational |

### DeepSeek

| Model | Params | Notes |
|---|---|---|
| `deepseek-ai/deepseek-r1-distill-qwen-1.5b` | 1.5B | R1 distilled (Qwen base) |
| `deepseek-ai/deepseek-r1-distill-qwen-7b` | 7B | R1 distilled (Qwen base) |
| `deepseek-ai/deepseek-r1-distill-qwen-14b` | 14B | R1 distilled (Qwen base) |
| `deepseek-ai/deepseek-r1-distill-llama-8b` | 8B | R1 distilled (Llama base) |
| `deepseek-ai/deepseek-llm-7b-base` | 7B | Base |
| `deepseek-ai/deepseek-llm-7b-chat` | 7B | Chat |
| `deepseek-ai/deepseek-coder-6.7b-instruct` | 6.7B | Code-specialized |
| `valdemardi/deepseek-r1-distill-qwen-32b-awq` | 32B | R1 32B AWQ-quantized |
| `agentica-org/deepscaler-1.5b-preview` | 1.5B | RL-trained 1.5B reasoning |

### IBM Granite

| Model | Params | Notes |
|---|---|---|
| `ibm-granite/granite-3.1-8b-instruct` | 8B | Granite 3.1 instruct |
| `ibm-granite/granite-3.3-2b-instruct` | 2B | Granite 3.3 (smaller) |
| `ibm-granite/granite-3.3-8b-instruct` | 8B | Granite 3.3 instruct |
| `ibm-granite/granite-guardian-3.3-8b` | 8B | Safety/moderation |

### SmolLM (HuggingFace)

| Model | Params | Notes |
|---|---|---|
| `huggingfacetb/smollm2-135m` | 135M | **Smallest base in list** |
| `huggingfacetb/smollm2-135m-instruct` | 135M | **Smallest instruct in list — G-LIVE-1 recommendation** |
| `huggingfacetb/smollm2-360m-instruct` | 360M | Next tier up |
| `huggingfacetb/smollm2-1.7b-instruct` | 1.7B | Largest SmolLM |

### Specialized / niche

| Model | Params | Notes |
|---|---|---|
| `openai-community/gpt2` | 124M | Legacy reference |
| `distilbert/distilgpt2` | 82M | Smaller GPT-2 distill |
| `tiiuae/falcon-7b-instruct` | 7B | Falcon |
| `bigcode/starcoder` | 15.5B | Code generation |
| `bigcode/starcoder2-15b` | 15B | Code generation v2 |
| `defog/sqlcoder-7b-2` | 7B | SQL-specialized |
| `jinaai/readerlm-v2` | 1.5B | HTML→Markdown extraction |
| `mixedbread-ai/mxbai-rerank-base-v2` | ~135M | Reranking (not text generation) |
| `mixedbread-ai/mxbai-rerank-large-v2` | ~570M | Reranking large |
| `livekit/turn-detector` | ~50M | Voice turn detection |
| `ucsb-surfi/vulnllm-r-7b` | 7B | Security/CVE-specialized |
| `fdtn-ai/foundation-sec-8b` | 8B | Security base |
| `fdtn-ai/foundation-sec-8b-instruct` | 8B | Security instruct |
| `kakaocorp/kanana-safeguard-8b` | 8B | Korean safety |
| `kakaocorp/kanana-1.5-8b-instruct-2505` | 8B | Korean instruct |
| `kblueleaf/tipo-500m-ft` | 500M | Prompt optimization |
| `m-a-p/yue-s1-7b-anneal-en-cot` | 7B | Music generation |
| `sarvamai/sarvam-1` | 2B | Indic languages |
| `sarvamai/sarvam-m` | 7B | Indic languages (larger) |
| `bllossom/llama-3.2-korean-bllossom-3b` | 3B | Korean Llama |
| `allam-ai/allam-7b-instruct-preview` | 7B | Arabic |
| `utter-project/eurollm-1.7b` | 1.7B | Multilingual European |
| `speakleash/bielik-1.5b-v3.0-instruct` | 1.5B | Polish |
| `uer/gpt2-chinese-cluecorpussmall` | ~124M | Chinese GPT-2 |
| `skt/a.x-4.0-light` | unknown | Korean |
| `k-intelligence/midm-2.0-base-instruct` | unknown | Korean instruct |
| `k-intelligence/midm-2.0-mini-instruct` | unknown | Korean mini |
| `probemedicalyonseimailab/medllama3-v20` | 8B | Medical-specialized |
| `allenai/olmo-2-0425-1b-instruct` | 1B | AllenAI OLMo 2 |
| `lgai-exaone/exaone-3.5-2.4b-instruct` | 2.4B | LG EXAONE |
| `lgai-exaone/exaone-deep-7.8b` | 7.8B | EXAONE Deep |
| `nanbeige/nanbeige4.1-3b` | 3B | Nanbeige |
| `nvidia/llama-3.1-nemotron-nano-4b-v1.1` | 4B | NVIDIA Nemotron Nano |
| `nvidia/llama-3.1-nemotron-nano-8b-v1` | 8B | NVIDIA Nemotron Nano (larger) |

---

## How to use in `fabrik gpu rent`

1. Pick a model from the recommendation table above (Phase 1 G-LIVE-1: SmolLM2-135M-instruct).
2. RunPod creates a vLLM-backed endpoint serving that model. Capture the `templateId` from the resulting endpoint's settings page.
3. Add to `/opt/fabrik/.env.sysadmin`:

   ```bash
   RUNPOD_API_KEY=<your-runpod-key>
   MAX_DAILY_GPU_COST=50
   RUNPOD_SERVERLESS_TEMPLATE_ID=<the-template-id>
   ```

4. Call from Fabrik:

   ```python
   from fabrik.orchestrator.gpu_rent import rent

   def use_endpoint(endpoint):
       # endpoint.url is the OpenAI-compatible /v1/chat/completions endpoint
       ...

   rent("serverless", workload="smoke", work_fn=use_endpoint, max_cost_usd=1.0)
   ```

   Or from the CLI:

   ```bash
   fabrik gpu rent serverless --workload smoke-test --max-cost 1
   ```

---

## When to re-verify this list

- Before any new `fabrik gpu` Phase 1 release.
- Before swapping the production `RUNPOD_SERVERLESS_TEMPLATE_ID` to a different model.
- Quarterly (audit step on the calendar).
- If a Phase 1 G-LIVE-1 drill fails with "model not found" — the model may have been removed by RunPod.

## Notes

- All models above are **vLLM-served** under RunPod's HF deployment flow. vLLM is the rule's default per [`76-gpu-workers.md`](../../.windsurf/rules/core/76-gpu-workers.md) line 183.
- "Params" column is best-effort from HF model card; in some cases (Korean models, Asian-team models) the cards don't always declare clean param counts.
- Some models above (rerank models, turn-detector, music gen) aren't text-generation LLMs — they're listed because RunPod's HF flow accepts them, but they won't work for chat-completion smoke tests.
- For non-LLM workloads (image gen, audio, custom CUDA), use the **Docker image** deployment path or **Pods** (`--kind pod-*`), not this list.
