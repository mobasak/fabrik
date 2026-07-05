# OpenRouter API Reference

> **Live-grounded 2026-07-05.** Every fact below was fetched *this session* from `openrouter.ai/docs` (URLs cited inline + in Sources), by four parallel research subagents — **not from model memory.** Refresh by re-fetching the Sources (or re-running the research pass); **re-verify pricing / rate limits before relying on them** — those drift fastest. This is the canonical internal reference for the OpenRouter-using modules (`ai-consult`, `code-agent`, the recruit/subagents runtime). `/fabrik-spec-review` checks a spec's OpenRouter claims against *this* file (and re-verifies it live if stale).

**Base endpoint:** `POST https://openrouter.ai/api/v1/chat/completions` — OpenAI-compatible, Bearer auth. Full OpenAPI at `https://openrouter.ai/openapi.yaml`.

## ⚠️ Read-first gotchas (things that changed — you will write bugs if you code from memory)

- **`usage: {include:true}` and `stream_options: {include_usage:true}` are DEPRECATED no-ops.** Full usage (cost, cached tokens, reasoning tokens) now ships **automatically** on every response, streaming or not. Never gate usage-parsing on sending them.
- **Message compression is the `plugins: [{"id":"context-compression"}]` plugin, NOT the legacy `transforms: ["middle-out"]` field.** The old top-level `transforms` array is not in the current `Request` type.
- **Auto Exacto:** any request containing `tools` is automatically re-ordered by throughput / tool-call success / benchmarks, *overriding* price ordering — set `provider.sort:"price"` (or `:floor`) to opt back into price.
- **Provider routing has grown** well past `only/order/sort`: `ignore`, `zdr`, `enforce_distillable_text`, `preferred_min_throughput`/`preferred_max_latency` (percentile objects), `max_price`, `quantizations`, and a `sort` **object** form (`by`/`partition`).
- **Stream cancellation only stops billing for an allow-list of providers** (see §2); for the rest, and for all non-streaming requests, you're billed for the full response even if you abort.

---

## 1. Request & response basics

OpenRouter normalizes request/response schemas across all providers so client code targets one shape. Base endpoint `POST https://openrouter.ai/api/v1/chat/completions`. Auth: `Authorization: Bearer <OPENROUTER_API_KEY>` + `Content-Type: application/json`. You can also point the OpenAI SDK's `baseURL` at `https://openrouter.ai/api/v1`. [or-docs](https://openrouter.ai/docs/api/reference/authentication)

### App-attribution headers (OpenRouter-specific, not OpenAI)

| Header | Purpose |
|---|---|
| `HTTP-Referer` | Your app's site URL — used for the public rankings on openrouter.ai |
| `X-OpenRouter-Title` (alias `X-Title`) | App display title on the OpenRouter dashboard |
| `X-OpenRouter-Categories` | Marketplace categories for your app |
| `X-OpenRouter-Metadata: enabled` (legacy `X-OpenRouter-Experimental-Metadata`) | Opt in to `openrouter_metadata` (routing/guardrail context) on the response, incl. error responses |

[or-docs](https://openrouter.ai/docs/api/reference/overview)

### Core request body (`Request` type, verbatim from docs)

```typescript
type Request = {
  messages?: Message[];        // either messages OR prompt is required
  prompt?: string;
  model?: string;              // omitted → account/payer default

  response_format?: ResponseFormat;   // §7 structured outputs
  stop?: string | string[];
  stream?: boolean;
  plugins?: Plugin[];          // web, file-parser, response-healing, context-compression (§6), auto-router (§4)

  max_tokens?: number;         // [1, context_length); SDK notes deprecation in favor of max_completion_tokens; some providers min 16
  temperature?: number;        // [0, 2], default 1.0
  tools?: Tool[];              // §8
  tool_choice?: ToolChoice;

  seed?: number;                    // integer — deterministic sampling attempt
  top_p?: number;                   // (0, 1], default 1.0
  top_k?: number;                   // [1, ∞) — ignored for OpenAI models
  frequency_penalty?: number;       // [-2, 2]
  presence_penalty?: number;        // [-2, 2]
  repetition_penalty?: number;      // (0, 2]
  logit_bias?: { [key: number]: number };
  top_logprobs: number;
  min_p?: number;                   // [0, 1]
  top_a?: number;                   // [0, 1]
  prediction?: { type: 'content'; content: string }; // predicted-output latency optimization

  // OpenRouter-only routing:
  models?: string[];          // §4 fallback list
  route?: 'fallback';         // present in the Request type; not described on the routing pages (as of 2026-07-05)
  provider?: ProviderPreferences;  // §3
  user?: string;               // stable end-user id for abuse detection
  debug?: { echo_upstream_body?: boolean }; // streaming-only, dev use (§11)
};
```
[or-docs](https://openrouter.ai/docs/api/reference/overview) · [or-docs](https://openrouter.ai/docs/api/reference/parameters)

**OpenAI-compatible passthrough:** `model`, `messages`/`prompt`, `max_tokens`, `temperature`, `top_p`, `stop`, `seed`, `tools`, `tool_choice`, `response_format`, `frequency_penalty`, `presence_penalty`, `logit_bias`, `stream`. **OpenRouter-specific:** `models`, `route:'fallback'`, `provider`, `plugins`, `user`, `debug`. **Extended sampling (provider-dependent):** `top_k`, `repetition_penalty`, `min_p`, `top_a`. Unsupported params for the chosen model are **silently ignored**, not errored (unless `provider.require_parameters:true`, §3).

### Response (non-streaming)

```typescript
type Response = {
  id: string;                  // "gen-xxxx" — usable at GET /api/v1/generation?id= (§9)
  choices: Choice[];
  created: number;             // unix ts
  model: string;               // the model that ACTUALLY served (matters with §4 fallback)
  object: 'chat.completion' | 'chat.completion.chunk';
  system_fingerprint?: string;
  usage?: ResponseUsage;       // always present non-streaming (§9)
};
type NonStreamingChoice = {
  finish_reason: string | null;         // normalized: tool_calls | stop | length | content_filter | error
  native_finish_reason: string | null;  // raw provider value
  message: { content: string | null; role: string; tool_calls?: ToolCall[] };
  error?: ErrorResponse;
};
```
`finish_reason` is **normalized** to `tool_calls | stop | length | content_filter | error`; the raw provider value is preserved as `native_finish_reason`. Token counts use each model's **native tokenizer**; pricing is on those native counts. **Assistant prefill:** append a trailing `{role:"assistant", content:"..."}` to continue/guide output. [or-docs](https://openrouter.ai/docs/api/reference/overview)

---

## 2. Streaming (SSE)

`stream: true` → `text/event-stream`. Supported for *any* model (OpenRouter normalizes streaming even for non-streaming upstreams). [or-docs](https://openrouter.ai/docs/api/reference/streaming)

**Wire format** — each chunk is a `data: {chat.completion.chunk}` line; the stream ends with a literal `data: [DONE]`. Streaming choices carry `delta` (not `message`): `{ content: string|null; role?: string; tool_calls?: ToolCall[] }`.

```
data: {"id":"gen-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"gen-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

: OPENROUTER PROCESSING

data: {"id":"gen-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop","native_finish_reason":"stop"}]}

data: {"id":"gen-abc","object":"chat.completion.chunk","choices":[],"usage":{"prompt_tokens":10,"completion_tokens":4,"total_tokens":14}}

data: [DONE]
```
(Assembled from the documented delta/chunk/usage/`[DONE]` shapes + the literal comment example — see Sources.)

- **Comment/heartbeat lines** `: OPENROUTER PROCESSING` are SSE comments (lines starting `:`) sent to prevent timeouts — a spec-compliant parser ignores them. OpenRouter **warns against hand-rolled `JSON.parse` per line** and recommends `eventsource-parser`, the OpenAI SDK, or the Vercel AI SDK.
- **Terminal `usage`** arrives exactly once, in the final chunk, with an **empty `choices` array**, immediately before `data: [DONE]`.
- **`finish_reason`** is `null` mid-stream; set (normalized + `native_finish_reason`) on the final delta chunk.
- **`X-Generation-Id`** response header is returned on all endpoints for correlating to `/api/v1/generation` (§9).
- **`stream_options: {include_usage:true}` is deprecated / no-op** — usage ships automatically (see gotchas + §9).

**Stream cancellation** — aborting the connection (`AbortController` / closing the response) cancels the stream. **Billing stops immediately only for an allow-list of providers**; for the rest (and all non-streaming requests) the model runs server-side and you're billed for the full response. [or-docs](https://openrouter.ai/docs/api/reference/streaming)
- *Cancellation-supported:* OpenAI, Azure, Anthropic, Fireworks, Mancer, Recursal, AnyScale, Lepton, OctoAI, Novita, DeepInfra, Together, Cohere, Hyperbolic, Infermatic, Avian, XAI, Cloudflare, SFCompute, Nineteen, Liquid, Friendli, Chutes, DeepSeek.
- *Not supported:* AWS Bedrock, Groq, Modal, Google, Google AI Studio, Minimax, HuggingFace, Replicate, Perplexity, Mistral, AI21, Featherless, Lynn, Lambda, Reflection, SambaNova, Inflection, ZeroOneAI, AionLabs, Alibaba, Nebius, Kluster, Targon, InferenceNet.

**Mid-stream errors** — once ≥1 token is flushed the HTTP status is committed `200`; the error rides in-band as a terminal-shaped SSE chunk (`"error":{...}`, `finish_reason:"error"`) then the stream ends (no further chunks / `[DONE]`). See §11.

---

## 3. Provider routing (`provider` object)

Default (no `sort`/`order`): OpenRouter load-balances across providers — (1) skip providers with outages in the last 30s; (2) weight by **inverse-square of price**; (3) hold the rest as fallbacks. Setting `tools`/`tool_choice` or `max_tokens` restricts routing to providers supporting them. [or-docs](https://openrouter.ai/docs/guides/routing/provider-selection)

| Field | Type | Default | Behavior |
|---|---|---|---|
| `order` | `string[]` | – | Provider slugs to try in order; **disables load balancing** |
| `allow_fallbacks` | `boolean` | `true` | `false` = only primary/custom list; fail if unavailable |
| `require_parameters` | `boolean` | `false` | `true` = exclude providers that don't support all supplied params (default: they get the request and ignore unsupported params) |
| `data_collection` | `"allow"\|"deny"` | `"allow"` | `deny` = only providers that don't store/train on data; merges with account setting |
| `zdr` | `boolean` | unset | `true` = Zero-Data-Retention endpoints only; OR with account ZDR (can only *add* enforcement) |
| `enforce_distillable_text` | `boolean` | unset | `true` = only models whose author allows text distillation |
| `only` | `string[]` | – | Whitelist provider slugs (merges with account allow-list) |
| `ignore` | `string[]` | – | Blacklist provider slugs (merges with account ignore-list) |
| `quantizations` | `string[]` | – | Filter by quant: `int4,int8,fp4,fp6,fp8,fp16,bf16,fp32,unknown` |
| `sort` | `string\|object` | – | `"price"\|"throughput"\|"latency"` OR object (below); **disables load balancing** |
| `preferred_min_throughput` | `number\|object` | – | Min tok/s; number = p50; object = percentile cutoffs. **Deprioritizes, never excludes** |
| `preferred_max_latency` | `number\|object` | – | Max latency (s); same number/percentile shape; deprioritize-not-exclude |
| `max_price` | `object` | – | `{prompt, completion, request, image}` caps — **CAN block the request** if unmet |

**`sort` object form** (for cross-model sorting with `models`, §4): `{ by: "price"\|"throughput"\|"latency", partition: "model"(default) \| "none" }`. `partition:"model"` tries the primary model's endpoints first regardless of perf; `partition:"none"` sorts endpoints globally across all listed models.

**Percentiles** (`preferred_*`): tracked per model+provider over a rolling **5-min window** — `p50/p75/p90/p99`. Multiple cutoffs = ALL must be met to be "preferred."

**Provider-slug matching** (`order`/`only`/`ignore`): base slug (`google-vertex`) matches all variants/regions; suffixed slug (`google-vertex/us-east5`, `deepinfra/turbo`) targets that specific one. Copy the exact slug from the model's detail page.

**Anthropic beta passthrough** (`x-anthropic-beta: <value>[,<value>]`): `interleaved-thinking-2025-05-14` (thinking interleaved with output); `structured-outputs-2025-11-13` (**required** to keep `strict:true` on tools — without it OR strips `strict`).

**Shortcuts:** `:nitro` ≡ `provider.sort:"throughput"`; `:floor` ≡ `provider.sort:"price"` (model-slug suffixes, e.g. `openai/gpt-5.2:nitro`).

**Auto Exacto** (⚠️ gotcha): any request with `tools` is auto-reordered by real-time throughput / tool-call success / benchmark signals instead of price — runs automatically, no config. Opt back into price with `provider.sort:"price"`, `:floor`, or an account default. [or-docs](https://openrouter.ai/docs/guides/routing/auto-exacto)

```json
{ "model":"x", "messages":[...], "provider": { "sort": { "by":"price", "partition":"none" }, "preferred_min_throughput": { "p90": 50 }, "max_price": { "prompt": 1, "completion": 2 } } }
```
`route` param: not documented on the routing pages (though present in the `Request` type, §1). [or-docs](https://openrouter.ai/docs/guides/routing/provider-selection)

---

## 4. Model routing

**`models: string[]`** — fallback models in priority order; if the primary `model` errors (context-length, moderation on filtered models, rate-limit, downtime), OR tries the next. Billed at whichever model **actually served** (top-level `model` in the response). Distinct from *provider* fallback (`provider.allow_fallbacks`, which falls through providers *within* one model). Via the OpenAI SDK, pass `models` in `extra_body`. [or-docs](https://openrouter.ai/docs/guides/routing/model-fallbacks)

**Anthropic Messages API (`/api/v1/messages`)** uses `fallbacks: [{"model": ...}]` instead — each entry accepts **only** `model` (per-attempt overrides → HTTP 400), **max 3 entries**, can't combine with `models`. OpenRouter does the fallback itself (not Anthropic's server-side feature).

**Auto Router** — `"model": "openrouter/auto"` (powered by NotDiamond): analyzes the prompt → picks the best model → returns which in the top-level `model`. Curated pool (snapshot Dec 2025): Claude Sonnet 4.5, Claude Opus 4.5, GPT-5.1, Gemini 3.1 Pro, DeepSeek 3.2, + others. Standard price for whichever model runs; requires `messages` (not `prompt`); streaming + tools work.
- **Session stickiness** (keeps prompt-cache warm): *implicit* (fingerprint of first system+user msg; pins once cache usage reported) or *explicit* `session_id` (pins on first success). Cache expires after **5 min** idle.
- **Restrict the pool** via `plugins: [{"id":"auto-router", "allowed_models": ["anthropic/*","openai/gpt-5.1"], "cost_quality_tradeoff": 3}]` — `allowed_models` wildcard patterns; `cost_quality_tradeoff` integer `0` (pure quality) → `10` (cheapest), default `7`.

[or-docs](https://openrouter.ai/docs/guides/routing/routers/auto-router) · [or-docs](https://openrouter.ai/docs/guides/routing/model-fallbacks)

---

## 5. Reasoning tokens (`reasoning` object)

| Field | Type | Values | Default | Behavior |
|---|---|---|---|---|
| `reasoning.effort` | string | `max,xhigh,high,medium,low,minimal,none` | none (excl. w/ `max_tokens`) | Budget as fraction of `max_tokens` (max/xhigh≈95%, high≈80%, medium≈50%, low≈20%, minimal≈10%, none=off) |
| `reasoning.max_tokens` | int | ≥1024 (Anthropic ≤128000) | none | Direct token budget (Anthropic, Gemini thinking, some Qwen); can't combine w/ `effort` |
| `reasoning.exclude` | bool | true/false | `false` | Model still reasons but content withheld; **all models support this** |
| `reasoning.enabled` | bool | true/false | inferred | Explicit `true` = reasoning at medium effort/defaults |

Legacy top-level aliases: `reasoning_effort` (= `reasoning.effort`), `include_reasoning` (deprecated, inverted `reasoning.exclude`). **Response:** `message.reasoning` (string) + `message.reasoning_details[]` (`type` = `reasoning.summary`/`reasoning.encrypted`/`reasoning.text`, `format`, `id`, `index`). **Billed as output/completion tokens** → `usage.completion_tokens_details.reasoning_tokens`. Per-model: OpenAI o-series supports `effort` but **doesn't return** reasoning; Anthropic `max_tokens` (`:thinking` slug deprecated → use `reasoning`); Gemini 3 maps effort→thinkingLevel; DeepSeek R1 / Grok support `effort`. [or-docs](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)

---

## 6. Message transforms → context-compression plugin

⚠️ The current mechanism is the **`plugins` array with `id:"context-compression"`** ("middle-out"), **not** a top-level `transforms: ["middle-out"]` field (that form is legacy/community, not in the current `Request` type). [or-docs](https://openrouter.ai/docs/guides/features/message-transforms) · [or-docs](https://openrouter.ai/docs/api/reference/overview)

```json
{ "plugins": [{ "id": "context-compression" }] }          // enable
{ "plugins": [{ "id": "context-compression", "enabled": false }] }  // disable
```
- Compresses prompts exceeding context by removing/truncating **middle** messages (LLMs attend less to the middle) until it fits. `plugins[].enabled` default `true` when present; compression engine enum = `middle-out` (only value).
- **Message-count caps** (e.g. Anthropic): keeps half the messages from start + half from end.
- **Routing:** with compression on, OR prefers models with context ≥ half the required tokens, else the largest-context model, then compresses to fit.
- **Auto-default:** endpoints with **≤8,192-token** context use compression automatically; opt out with `enabled:false` (then over-length requests error).

---

## 7. Structured outputs (`response_format`)

| Field | Type | Behavior |
|---|---|---|
| `response_format` | `{type:"json_object"}` \| `{type:"json_schema", json_schema:{...}}` | Forces output shape |
| `json_schema.name` | string | Schema identifier |
| `json_schema.strict` | bool | **Always set `strict:true`** to force exact adherence |
| `json_schema.schema` | JSON Schema | `properties` (+`description`), `required[]`, `additionalProperties:false` |

Check support via the model's `supported_parameters` containing `structured_outputs` (or `openrouter.ai/models?supported_parameters=structured_outputs`, or `provider.require_parameters:true`). Support: OpenAI (GPT-4o+), Gemini, Anthropic (Sonnet 4.5 / Opus 4.1+), most OSS, Fireworks. **Unsupported → the request errors** (no auto-fallback to plain JSON; the separate `response-healing` plugin mitigates malformed JSON but is not a structured-outputs fallback). [or-docs](https://openrouter.ai/docs/guides/features/structured-outputs)

```json
{ "response_format": { "type":"json_schema", "json_schema": { "name":"weather", "strict":true,
  "schema": { "type":"object", "properties": { "location":{"type":"string"}, "temperature":{"type":"number"} },
  "required":["location","temperature"], "additionalProperties":false } } } }
```

---

## 8. Tool calling (the load-bearing section for `code-agent`)

The model **never executes** anything — it emits a structured request; your code runs it and returns the result. OpenRouter normalizes tools to the OpenAI shape across providers. Supported models: `openrouter.ai/models?supported_parameters=tools`. **`tools` must be sent on EVERY request in the conversation** (OR validates the schema each call). [or-docs](https://openrouter.ai/docs/guides/features/tool-calling)

```typescript
type Tool = { type: 'function'; function: { name: string; description?: string; parameters: object /*JSON Schema*/ } };
type ToolChoice = 'none' | 'auto' | { type: 'function'; function: { name: string } };
// tool_choice also accepts 'required' (documented in the Parameters ref though omitted from the published ToolChoice type — safe to send)
// parallel_tool_calls?: boolean (default true)
```

**The loop** a coding agent runs:
1. Send request with `tools`.
2. Model returns `finish_reason:"tool_calls"` + an assistant message with `tool_calls[]` = `{id, type:"function", function:{name, arguments}}`. **`arguments` is a JSON-encoded STRING** — `JSON.parse` it. Append this assistant message to history **verbatim**.
3. Execute the tool(s) locally; for each, append `{role:"tool", tool_call_id:<matching id>, content:<JSON-stringified result>, name?}`.
4. Re-send the **entire** conversation + the `tools` array again → model synthesizes a normal message (or calls more tools). Loop; **cap max iterations**.

```typescript
while (iter++ < MAX) {
  const r = await send({ model, tools, messages, stream:false });
  messages.push(r.choices[0].message);                 // easy to forget
  const tc = r.choices[0].message.tool_calls;
  if (!tc) break;                                       // final answer
  for (const call of tc)                                // parallel_tool_calls → may be >1
    messages.push({ role:"tool", tool_call_id:call.id,
      content: JSON.stringify(await TOOLS[call.function.name](JSON.parse(call.function.arguments))) });
}
```

- **`parallel_tool_calls`** (default `true`): `tool_calls[]` may hold >1; execute all, append one `role:"tool"` per `tool_call_id`. Set `false` for strictly one-per-turn.
- **Streaming tool calls:** `delta.tool_calls` fragments arrive across chunks; **accumulate keyed by `delta.tool_calls[].index`** (OpenAI-compat streaming multiplexes parallel calls by `index`; not shown on an OR-owned page as of 2026-07-05 — corroborated by a third-party client), until `finish_reason:"tool_calls"`. Anthropic gets `eager_input_streaming:true` auto-applied (incremental arg chunks).
- **Reliability:** OR tracks a per-provider **Tool Call Error Rate** (drives Auto Exacto, §3). **Interleaved thinking:** some models (e.g. Claude Sonnet 4.5) reason *between* tool calls — more tokens + latency.

[or-docs](https://openrouter.ai/docs/guides/features/tool-calling) · [or-docs](https://openrouter.ai/docs/api/reference/parameters)

---

## 9. Usage accounting

Detailed usage is **always included automatically** (streaming: final chunk with empty `choices`, right before `[DONE]`; non-streaming: top-level `usage`). `usage:{include:true}` / `stream_options:{include_usage:true}` are **deprecated no-ops**. [or-docs](https://openrouter.ai/docs/cookbook/administration/usage-accounting) · [or-docs](https://openrouter.ai/docs/api/reference/overview)

```typescript
type ResponseUsage = {
  prompt_tokens: number;       // incl. images, input audio, tools
  completion_tokens: number;
  total_tokens: number;
  prompt_tokens_details?: { cached_tokens: number; cache_write_tokens?: number; audio_tokens?: number; video_tokens?: number };
  completion_tokens_details?: { reasoning_tokens?: number; audio_tokens?: number; image_tokens?: number };
  cost?: number;               // credits charged
  is_byok?: boolean;
  cost_details?: { upstream_inference_cost?: number; upstream_inference_prompt_cost: number; upstream_inference_completions_cost: number };
  server_tool_use?: { web_search_requests?: number };
};
```
Native tokenizer per model; cost is on native counts. **Async lookup:** `GET https://openrouter.ai/api/v1/generation?id=<gen-id>` (Bearer) returns fuller stats (`total_cost`, `cache_discount`, `native_tokens_*`, `provider_name`, latencies, …). ⚠️ Via this endpoint `upstream_inference_cost` is only populated for **BYOK** requests (else `0`/`null`). [or-docs](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)

---

## 10. Prompt caching

Two modes by provider: **automatic/implicit** (no request change — OpenAI, DeepSeek, Gemini 2.5, Grok/xAI, Groq Kimi K2, Moonshot) vs **explicit breakpoints** via `cache_control:{"type":"ephemeral"}` (Anthropic Claude, Alibaba Qwen). [or-docs](https://openrouter.ai/docs/guides/best-practices/prompt-caching)

| Provider | Mode | Write | Read | Notes |
|---|---|---|---|---|
| OpenAI | Auto | – | 0.25–0.5x | min 1024 tok |
| DeepSeek | Auto | 1.0x | 0.1x | |
| Gemini 2.5 | Implicit | input + 5-min storage | 0.25x | min 1024–4096 tok |
| Grok/xAI | Auto | – | 0.25x | |
| Groq | Auto | – | 0.5x | Kimi K2 |
| Moonshot | Auto | – | 0.25x | |
| Anthropic | Explicit | 1.25x (5m) / 2x (1h) | 0.1x | max 4 breakpoints |
| Alibaba Qwen | Explicit | 1.25x | 0.1x | 5-min TTL only |

- **Top-level `cache_control`** (Anthropic only): auto-applies a breakpoint to the last cacheable block, advancing as the convo grows. ⚠️ Only works routing **direct to Anthropic** — presence excludes Bedrock/Vertex. Per-block `cache_control` works across all Anthropic-compatible providers incl. Bedrock/Vertex.
- **Per-block:** `{"type":"text","text":"...","cache_control":{"type":"ephemeral","ttl":"1h"}}` — max **4 breakpoints**. TTL: `ephemeral` = 5 min (default); `ttl:"1h"` = 1 hour (Anthropic/Gemini only).
- **Sticky routing:** after a cached request OR pins the provider to keep the cache warm; control with `session_id` (≤256 chars) body field or `x-session-id` header.
- **Inspect savings:** Activity page · `GET /api/v1/generation?id=` (`cache_discount`) · `usage.prompt_tokens_details` (`cached_tokens` read, `cache_write_tokens` write). Anthropic reports negative discount on writes, positive on reads. Gemini: put dynamic content in `user` messages (system is normalized to one immutable block).

---

## 11. Rate limits & errors

```typescript
type ErrorResponse = { error: { code: number; message: string; metadata?: Record<string, unknown> } };
```
HTTP status == `error.code` when the request itself failed; if generation already started, status is `200` and the error is in-body / mid-stream (§2). [or-docs](https://openrouter.ai/docs/api/reference/errors-and-debugging)

| Status | Meaning | | Status | Meaning |
|---|---|---|---|---|
| 400 | bad/missing params, CORS | | 429 | rate limited |
| 401 | invalid credentials | | 502 | model down / invalid response |
| 402 | insufficient credits | | 503 | no provider meets routing reqs |
| 403 | permission / guardrail / moderation | | 408 | request timeout |

**`Retry-After`** header on 429/503 (seconds) — honored by the OpenAI/Anthropic/Vercel/OpenRouter SDKs; for raw fetch, sleep `Retry-After*1000` and retry.

**Rate limits & credits** ([or-docs](https://openrouter.ai/docs/api/reference/limits)): account-level, **global** (extra keys don't raise it), differ per model. `:free` variants: **20 req/min**; daily cap 50/day (<10 credits ever) or 1000/day (≥10). Negative balance → 402 (incl. free). Check via `GET /api/v1/key` (`limit`, `limit_remaining`, `limit_reset`, `usage*`, `is_free_tier`; the `rate_limit` object is **deprecated, returns -1**). Paid models have **no OR-enforced hard limit** (only free-tier caps + Cloudflare DDoS). ⚠️ Per-request `x-ratelimit-*` headers are **not** documented on official pages (third-party claims unverified).

**Typed `error_type`** (in `error.metadata.error_type`, stable across streaming/non-streaming; raw upstream in `provider_code` for non-500s):

| `error_type` | HTTP | | `error_type` | HTTP |
|---|---|---|---|---|
| `context_length_exceeded` | 400 | | `rate_limit_exceeded` | 429 |
| `max_tokens_exceeded` | 400 | | `provider_overloaded` | 503 |
| `token_limit_exceeded` | 400 | | `provider_unavailable` | 502 |
| `string_too_long` | 400 | | `invalid_request` / `invalid_prompt` | 400 |
| `authentication` | 401 | | `not_found` | 404 |
| `permission_denied` | 403 | | `payload_too_large` | 413 |
| `payment_required` | 402 | | `unprocessable` | 422 |
| `content_policy_violation` / `refusal` | 400 | | `server` / `unmapped` | 500 |
| `invalid_image` / `image_too_large` / … | 400/404 | | `timeout` | 504 |

⚠️ **Length errors become successes:** `context_length_exceeded`, `max_tokens_exceeded`, `token_limit_exceeded`, `string_too_long` are returned as a **successful** completion with `finish_reason:"length"` (Chat Completions), not an error. **Moderation (403):** `metadata` = `{reasons[], flagged_input(≤100 chars), provider_name, model_slug}`. **Guardrail (403):** blocks pre-provider; with `X-OpenRouter-Metadata: enabled` the body adds an `openrouter_metadata.pipeline[]` of guardrail stages. **Skin differences:** Chat Completions embeds error alongside partial content; Responses API collapses to a narrow `code` set but keeps `error_type`; Anthropic Messages maps to native `error.type` + adds `error_type`. **"No content generated"** (cold start): retry / switch provider — you may still be billed for prompt processing. **`debug:{echo_upstream_body:true}`** (streaming, dev only): echoes the transformed upstream body as the first chunk (best-effort redaction, not guaranteed). [or-docs](https://openrouter.ai/docs/api/reference/errors-and-debugging)

---

## Sources (all fetched 2026-07-05 — re-fetch to refresh)

- https://openrouter.ai/docs/api/reference/overview
- https://openrouter.ai/docs/api/reference/parameters
- https://openrouter.ai/docs/api/reference/authentication
- https://openrouter.ai/docs/api/reference/streaming
- https://openrouter.ai/docs/api/reference/errors-and-debugging
- https://openrouter.ai/docs/api/reference/limits
- https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key
- https://openrouter.ai/docs/guides/routing/provider-selection
- https://openrouter.ai/docs/guides/routing/model-fallbacks
- https://openrouter.ai/docs/guides/routing/routers/auto-router
- https://openrouter.ai/docs/guides/routing/model-variants/nitro
- https://openrouter.ai/docs/guides/routing/auto-exacto
- https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
- https://openrouter.ai/docs/guides/features/message-transforms
- https://openrouter.ai/docs/guides/features/structured-outputs
- https://openrouter.ai/docs/guides/features/tool-calling
- https://openrouter.ai/docs/guides/best-practices/prompt-caching
- https://openrouter.ai/docs/cookbook/administration/usage-accounting
- https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation
- Third-party (corroboration only, flagged inline): docs.rs/openrouter-rs (streaming tool-call `index` merge); OpenRouterTeam/ai-sdk-provider#154 (legacy `transforms` field)

> **Provenance:** authored by 4 parallel `general-purpose` research subagents (sonnet), each live-fetching via exa/WebFetch/firecrawl/context7 and returning cited markdown; merged + consistency-checked by the orchestrator (opus). Facts not on an OpenRouter-owned page are flagged inline. **Not from training memory.**
