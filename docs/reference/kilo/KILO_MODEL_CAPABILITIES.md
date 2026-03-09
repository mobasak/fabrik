# Kilo Model Capabilities Reference

**Last Updated:** 2026-03-09
**Total Models:** 328
**Total Providers:** 59

This document provides comprehensive capabilities and pricing for all models available through Kilo CLI.

---

## Quick Reference: Pricing Tiers

| Tier | Input Cost/1M | Output Cost/1M | Use Case |
|------|--------------|----------------|----------|
| **Free** | $0.00 | $0.00 | Prototyping, learning |
| **Economy** | $0.001-0.10 | $0.01-0.50 | Quick tasks, tests |
| **Standard** | $0.10-0.50 | $0.50-2.00 | Daily development |
| **Pro** | $0.50-3.00 | $3.00-15.00 | Production code |
| **Expert** | $3.00-10.00 | $10.00-30.00 | Complex analysis |
| **Apex** | $15.00+ | $100.00+ | Mission-critical |

---

## Capability Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Supported |
| ❌ | Not supported |
| 🧠 | Reasoning/thinking capability |
| 🔧 | Tool/function calling |
| 📎 | File attachments |
| 🖼️ | Image input |
| 🎤 | Audio input |
| 📄 | PDF input |

---

## Models by Provider

### OPENAI (57 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `gpt-oss-20b` | $0.030 | $0.140 | 131K | 🧠 🔧 |
| `gpt-oss-120b` | $0.039 | $0.190 | 131K | 🧠 🔧 |
| `gpt-oss-120b:exacto` | $0.039 | $0.190 | 131K | 🧠 🔧 |
| `gpt-5-nano` | $0.050 | $0.400 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-oss-safeguard-20b` | $0.075 | $0.300 | 131K | 🧠 🔧 |
| `gpt-4.1-nano` | $0.100 | $0.400 | 1047K | 🔧 📎 🖼️ |
| `gpt-4o-mini` | $0.150 | $0.600 | 128K | 🔧 📎 🖼️ |
| `gpt-4o-mini-2024-07-18` | $0.150 | $0.600 | 128K | 🔧 📎 🖼️ |
| `gpt-4o-mini-search-preview` | $0.150 | $0.600 | 128K | - |
| `gpt-5-mini` | $0.250 | $2.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-5.1-codex-mini` | $0.250 | $2.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-4.1-mini` | $0.400 | $1.600 | 1047K | 🔧 📎 🖼️ |
| `gpt-3.5-turbo` | $0.500 | $1.500 | 16K | 🔧 |
| `gpt-audio-mini` | $0.600 | $2.400 | 128K | 🎤 |
| `gpt-3.5-turbo-0613` | $1.000 | $2.000 | 4K | 🔧 |
| `o3-mini` | $1.100 | $4.400 | 200K | 🔧 |
| `o3-mini-high` | $1.100 | $4.400 | 200K | 🔧 |
| `o4-mini` | $1.100 | $4.400 | 200K | 🧠 🔧 📎 🖼️ |
| `o4-mini-high` | $1.100 | $4.400 | 200K | 🧠 🔧 📎 🖼️ |
| `gpt-5` | $1.250 | $10.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-5-chat` | $1.250 | $10.000 | 128K | 📎 🖼️ |
| `gpt-5-codex` | $1.250 | $10.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-5.1` | $1.250 | $10.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-5.1-chat` | $1.250 | $10.000 | 128K | 🔧 📎 🖼️ |
| `gpt-5.1-codex` | $1.250 | $10.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-5.1-codex-max` | $1.250 | $10.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-3.5-turbo-instruct` | $1.500 | $2.000 | 4K | - |
| `gpt-5.2` | $1.750 | $14.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-5.2-chat` | $1.750 | $14.000 | 128K | 🔧 📎 🖼️ |
| `gpt-5.2-codex` | $1.750 | $14.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-5.3-chat` | $1.750 | $14.000 | 128K | 🔧 📎 🖼️ |
| `gpt-5.3-codex` | $1.750 | $14.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-4.1` | $2.000 | $8.000 | 1047K | 🔧 📎 🖼️ |
| `o3` | $2.000 | $8.000 | 200K | 🧠 🔧 📎 🖼️ |
| `o4-mini-deep-research` | $2.000 | $8.000 | 200K | 🧠 🔧 📎 🖼️ |
| `gpt-4o` | $2.500 | $10.000 | 128K | 🔧 📎 🖼️ |
| `gpt-4o-2024-08-06` | $2.500 | $10.000 | 128K | 🔧 📎 🖼️ |
| `gpt-4o-2024-11-20` | $2.500 | $10.000 | 128K | 🔧 📎 🖼️ |
| `gpt-4o-audio-preview` | $2.500 | $10.000 | 128K | 🔧 🎤 |
| `gpt-4o-search-preview` | $2.500 | $10.000 | 128K | - |
| `gpt-5.4` | $2.500 | $15.000 | 1050K | 🧠 🔧 📎 🖼️ |
| `gpt-audio` | $2.500 | $10.000 | 128K | 🎤 |
| `gpt-3.5-turbo-16k` | $3.000 | $4.000 | 16K | 🔧 |
| `gpt-4o-2024-05-13` | $5.000 | $15.000 | 128K | 🔧 📎 🖼️ |
| `gpt-4o:extended` | $6.000 | $18.000 | 128K | 🔧 📎 🖼️ |
| `gpt-4-1106-preview` | $10.000 | $30.000 | 128K | 🔧 |
| `gpt-4-turbo` | $10.000 | $30.000 | 128K | 🔧 📎 🖼️ |
| `gpt-4-turbo-preview` | $10.000 | $30.000 | 128K | 🔧 |
| `o3-deep-research` | $10.000 | $40.000 | 200K | 🧠 🔧 📎 🖼️ |
| `gpt-5-pro` | $15.000 | $120.000 | 400K | 🧠 🔧 📎 🖼️ |
| `o1` | $15.000 | $60.000 | 200K | 🔧 📎 🖼️ |
| `o3-pro` | $20.000 | $80.000 | 200K | 🧠 🔧 📎 🖼️ |
| `gpt-5.2-pro` | $21.000 | $168.000 | 400K | 🧠 🔧 📎 🖼️ |
| `gpt-4` | $30.000 | $60.000 | 8K | 🔧 |
| `gpt-4-0314` | $30.000 | $60.000 | 8K | 🔧 |
| `gpt-5.4-pro` | $30.000 | $180.000 | 1050K | 🧠 🔧 📎 🖼️ |
| `o1-pro` | $150.000 | $600.000 | 200K | 🧠 📎 🖼️ |

### QWEN (47 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `qwen3-vl-235b-a22b-thinking` | $0.000 | $0.000 | 131K | 🧠 🔧 📎 🖼️ |
| `qwen3-vl-30b-a3b-thinking` | $0.000 | $0.000 | 131K | 🧠 🔧 📎 🖼️ |
| `qwen2.5-coder-7b-instruct` | $0.030 | $0.090 | 32K | - |
| `qwen-turbo` | $0.033 | $0.130 | 131K | 🔧 |
| `qwen-2.5-7b-instruct` | $0.040 | $0.100 | 32K | 🔧 |
| `qwen3-8b` | $0.050 | $0.400 | 40K | 🧠 🔧 |
| `qwen3-30b-a3b-thinking-2507` | $0.051 | $0.340 | 32K | 🧠 🔧 |
| `qwen3-14b` | $0.060 | $0.240 | 40K | 🧠 🔧 |
| `qwen3-coder-30b-a3b-instruct` | $0.070 | $0.270 | 160K | 🔧 |
| `qwen3-235b-a22b-2507` | $0.071 | $0.100 | 262K | 🧠 🔧 |
| `qwen3-30b-a3b` | $0.080 | $0.280 | 40K | 🧠 🔧 |
| `qwen3-32b` | $0.080 | $0.240 | 40K | 🧠 🔧 |
| `qwen3-vl-8b-instruct` | $0.080 | $0.500 | 131K | 🔧 📎 🖼️ |
| `qwen3-30b-a3b-instruct-2507` | $0.090 | $0.300 | 262K | 🔧 |
| `qwen3-next-80b-a3b-instruct` | $0.090 | $1.100 | 262K | 🔧 |
| `qwen3.5-flash-02-23` | $0.100 | $0.400 | 1000K | 🧠 🔧 📎 🖼️ |
| `qwen3-vl-32b-instruct` | $0.104 | $0.416 | 131K | 🔧 📎 🖼️ |
| `qwen3-235b-a22b-thinking-2507` | $0.110 | $0.600 | 262K | 🧠 🔧 |
| `qwen3-vl-8b-thinking` | $0.117 | $1.365 | 131K | 🧠 🔧 📎 🖼️ |
| `qwen-2.5-72b-instruct` | $0.120 | $0.390 | 32K | 🔧 |
| `qwen3-coder-next` | $0.120 | $0.750 | 262K | 🔧 |
| `qwen3-vl-30b-a3b-instruct` | $0.130 | $0.520 | 131K | 🔧 📎 🖼️ |
| `qwen-vl-plus` | $0.137 | $0.410 | 131K | 📎 🖼️ |
| `qwen3-next-80b-a3b-thinking` | $0.150 | $1.200 | 128K | 🧠 🔧 |
| `qwq-32b` | $0.150 | $0.400 | 32K | 🧠 🔧 |
| `qwen3.5-35b-a3b` | $0.163 | $1.300 | 262K | 🧠 🔧 📎 🖼️ |
| `qwen3-coder-flash` | $0.195 | $0.975 | 1000K | 🔧 |
| `qwen3.5-27b` | $0.195 | $1.560 | 262K | 🧠 🔧 📎 🖼️ |
| `qwen2.5-vl-32b-instruct` | $0.200 | $0.600 | 128K | 📎 🖼️ |
| `qwen3-vl-235b-a22b-instruct` | $0.200 | $0.880 | 262K | 🔧 📎 🖼️ |
| `qwen-2.5-coder-32b-instruct` | $0.200 | $0.200 | 32K | - |
| `qwen-2.5-vl-7b-instruct` | $0.200 | $0.200 | 32K | 📎 🖼️ |
| `qwen3-coder` | $0.220 | $1.000 | 262K | 🔧 |
| `qwen3-coder:exacto` | $0.220 | $1.800 | 262K | 🔧 |
| `qwen-plus-2025-07-28` | $0.260 | $0.780 | 1000K | 🔧 |
| `qwen-plus-2025-07-28:thinking` | $0.260 | $0.780 | 1000K | 🧠 🔧 |
| `qwen3.5-122b-a10b` | $0.260 | $2.080 | 262K | 🧠 🔧 📎 🖼️ |
| `qwen3.5-plus-02-15` | $0.260 | $1.560 | 1000K | 🧠 🔧 📎 🖼️ |
| `qwen3.5-397b-a17b` | $0.390 | $2.340 | 262K | 🧠 🔧 📎 🖼️ |
| `qwen-plus` | $0.400 | $1.200 | 1000K | 🔧 |
| `qwen3-235b-a22b` | $0.455 | $1.820 | 131K | 🧠 🔧 |
| `qwen3-coder-plus` | $0.650 | $3.250 | 1000K | 🔧 |
| `qwen3-max-thinking` | $0.780 | $3.900 | 262K | 🧠 🔧 |
| `qwen-vl-max` | $0.800 | $3.200 | 131K | 🔧 📎 🖼️ |
| `qwen2.5-vl-72b-instruct` | $0.800 | $0.800 | 32K | 📎 🖼️ |
| `qwen-max` | $1.040 | $4.160 | 32K | 🔧 |
| `qwen3-max` | $1.200 | $6.000 | 262K | 🔧 |

### MISTRALAI (24 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `mistral-nemo` | $0.020 | $0.040 | 131K | 🔧 |
| `mistral-small-24b-instruct-2501` | $0.050 | $0.080 | 32K | 🔧 |
| `mistral-small-3.2-24b-instruct` | $0.060 | $0.180 | 131K | 🔧 📎 🖼️ |
| `devstral-small` | $0.100 | $0.300 | 131K | 🔧 |
| `ministral-3b-2512` | $0.100 | $0.100 | 131K | 🔧 📎 🖼️ |
| `mistral-small-creative` | $0.100 | $0.300 | 32K | 🔧 |
| `voxtral-small-24b-2507` | $0.100 | $0.300 | 32K | 🔧 🎤 |
| `mistral-7b-instruct-v0.1` | $0.110 | $0.190 | 2K | - |
| `ministral-8b-2512` | $0.150 | $0.150 | 262K | 🔧 📎 🖼️ |
| `ministral-14b-2512` | $0.200 | $0.200 | 262K | 🔧 📎 🖼️ |
| `mistral-saba` | $0.200 | $0.600 | 32K | 🔧 |
| `codestral-2508` | $0.300 | $0.900 | 256K | 🔧 |
| `mistral-small-3.1-24b-instruct` | $0.350 | $0.560 | 128K | 📎 🖼️ |
| `devstral-2512` | $0.400 | $2.000 | 262K | 🔧 |
| `devstral-medium` | $0.400 | $2.000 | 131K | 🔧 |
| `mistral-medium-3` | $0.400 | $2.000 | 131K | 🔧 📎 🖼️ |
| `mistral-medium-3.1` | $0.400 | $2.000 | 131K | 🔧 📎 🖼️ |
| `mistral-large-2512` | $0.500 | $1.500 | 262K | 🔧 📎 🖼️ |
| `mixtral-8x7b-instruct` | $0.540 | $0.540 | 32K | 🔧 |
| `mistral-large` | $2.000 | $6.000 | 128K | 🔧 |
| `mistral-large-2407` | $2.000 | $6.000 | 131K | 🔧 |
| `mistral-large-2411` | $2.000 | $6.000 | 131K | 🔧 |
| `mixtral-8x22b-instruct` | $2.000 | $6.000 | 65K | 🔧 |
| `pixtral-large-2411` | $2.000 | $6.000 | 131K | 🔧 📎 🖼️ |

### GOOGLE (19 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `gemma-3n-e4b-it` | $0.020 | $0.040 | 32K | - |
| `gemma-2-9b-it` | $0.030 | $0.090 | 8K | - |
| `gemma-3-27b-it` | $0.030 | $0.110 | 128K | 🔧 📎 🖼️ |
| `gemma-3-12b-it` | $0.040 | $0.130 | 131K | 📎 🖼️ |
| `gemma-3-4b-it` | $0.040 | $0.080 | 131K | 📎 🖼️ |
| `gemini-2.0-flash-lite-001` | $0.075 | $0.300 | 1048K | 🔧 📎 🖼️ 🎤 |
| `gemini-2.0-flash-001` | $0.100 | $0.400 | 1048K | 🔧 📎 🖼️ 🎤 |
| `gemini-2.5-flash-lite` | $0.100 | $0.400 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-2.5-flash-lite-preview-09-2025` | $0.100 | $0.400 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-3.1-flash-lite-preview` | $0.250 | $1.500 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-2.5-flash` | $0.300 | $2.500 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-3-flash-preview` | $0.500 | $3.000 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemma-2-27b-it` | $0.650 | $0.650 | 8K | - |
| `gemini-2.5-pro` | $1.250 | $10.000 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-2.5-pro-preview` | $1.250 | $10.000 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-2.5-pro-preview-05-06` | $1.250 | $10.000 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-3-pro-preview` | $2.000 | $12.000 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-3.1-pro-preview` | $2.000 | $12.000 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |
| `gemini-3.1-pro-preview-customtools` | $2.000 | $12.000 | 1048K | 🧠 🔧 📎 🖼️ 🎤 |

### META-LLAMA (15 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `llama-3.1-8b-instruct` | $0.020 | $0.050 | 16K | 🔧 |
| `llama-guard-3-8b` | $0.020 | $0.060 | 131K | - |
| `llama-3.2-1b-instruct` | $0.027 | $0.200 | 60K | - |
| `llama-3-8b-instruct` | $0.030 | $0.040 | 8K | 🔧 |
| `llama-3.2-11b-vision-instruct` | $0.049 | $0.049 | 131K | 📎 🖼️ |
| `llama-3.2-3b-instruct` | $0.051 | $0.340 | 80K | - |
| `llama-4-scout` | $0.080 | $0.300 | 327K | 🔧 📎 🖼️ |
| `llama-3.3-70b-instruct` | $0.100 | $0.320 | 131K | 🔧 |
| `llama-4-maverick` | $0.150 | $0.600 | 1048K | 🔧 📎 🖼️ |
| `llama-guard-4-12b` | $0.180 | $0.180 | 163K | 📎 🖼️ |
| `llama-guard-2-8b` | $0.200 | $0.200 | 8K | - |
| `llama-3.1-70b-instruct` | $0.400 | $0.400 | 131K | 🔧 |
| `llama-3-70b-instruct` | $0.510 | $0.740 | 8K | - |
| `llama-3.1-405b` | $4.000 | $4.000 | 32K | - |
| `llama-3.1-405b-instruct` | $4.000 | $4.000 | 131K | 🔧 |

### ANTHROPIC (13 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `claude-3-haiku` | $0.250 | $1.250 | 200K | 🔧 📎 🖼️ |
| `claude-3.5-haiku` | $0.800 | $4.000 | 200K | 🔧 📎 🖼️ |
| `claude-haiku-4.5` | $1.000 | $5.000 | 200K | 🧠 🔧 📎 🖼️ |
| `claude-3.7-sonnet` | $3.000 | $15.000 | 200K | 🧠 🔧 📎 🖼️ |
| `claude-3.7-sonnet:thinking` | $3.000 | $15.000 | 200K | 🧠 🔧 📎 🖼️ |
| `claude-sonnet-4` | $3.000 | $15.000 | 200K | 🧠 🔧 📎 🖼️ |
| `claude-sonnet-4.5` | $3.000 | $15.000 | 1000K | 🧠 🔧 📎 🖼️ |
| `claude-sonnet-4.6` | $3.000 | $15.000 | 1000K | 🧠 🔧 📎 🖼️ |
| `claude-opus-4.5` | $5.000 | $25.000 | 200K | 🧠 🔧 📎 🖼️ |
| `claude-opus-4.6` | $5.000 | $25.000 | 1000K | 🧠 🔧 📎 🖼️ |
| `claude-3.5-sonnet` | $6.000 | $30.000 | 200K | 🔧 📎 🖼️ |
| `claude-opus-4` | $15.000 | $75.000 | 200K | 🧠 🔧 📎 🖼️ |
| `claude-opus-4.1` | $15.000 | $75.000 | 200K | 🧠 🔧 📎 🖼️ |

### DEEPSEEK (12 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `deepseek-chat-v3.1` | $0.150 | $0.750 | 32K | 🧠 🔧 |
| `deepseek-chat-v3-0324` | $0.200 | $0.770 | 163K | 🧠 🔧 |
| `deepseek-v3.1-terminus` | $0.210 | $0.790 | 163K | 🧠 🔧 |
| `deepseek-v3.1-terminus:exacto` | $0.210 | $0.790 | 163K | 🧠 🔧 |
| `deepseek-v3.2` | $0.250 | $0.400 | 163K | 🧠 🔧 |
| `deepseek-v3.2-exp` | $0.270 | $0.410 | 163K | 🧠 🔧 |
| `deepseek-r1-distill-qwen-32b` | $0.290 | $0.290 | 32K | 🧠 |
| `deepseek-chat` | $0.320 | $0.890 | 163K | 🔧 |
| `deepseek-v3.2-speciale` | $0.400 | $1.200 | 163K | 🧠 |
| `deepseek-r1-0528` | $0.450 | $2.150 | 163K | 🧠 🔧 |
| `deepseek-r1` | $0.700 | $2.500 | 64K | 🧠 🔧 |
| `deepseek-r1-distill-llama-70b` | $0.700 | $0.800 | 131K | 🧠 |

### Z-AI (10 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `glm-4.7-flash` | $0.060 | $0.400 | 202K | 🧠 🔧 |
| `glm-4-32b` | $0.100 | $0.100 | 128K | 🔧 |
| `glm-4.5-air` | $0.130 | $0.850 | 131K | 🧠 🔧 |
| `glm-4.6v` | $0.300 | $0.900 | 131K | 🧠 🔧 📎 🖼️ |
| `glm-4.7` | $0.380 | $1.980 | 202K | 🧠 🔧 |
| `glm-4.6` | $0.390 | $1.900 | 204K | 🧠 🔧 |
| `glm-4.6:exacto` | $0.440 | $1.760 | 204K | 🧠 🔧 |
| `glm-4.5` | $0.600 | $2.200 | 131K | 🧠 🔧 |
| `glm-4.5v` | $0.600 | $1.800 | 65K | 🧠 🔧 📎 🖼️ |
| `glm-5` | $0.800 | $2.560 | 202K | 🧠 🔧 |

### X-AI (8 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `grok-4-fast` | $0.200 | $0.500 | 2000K | 🧠 🔧 📎 🖼️ |
| `grok-4.1-fast` | $0.200 | $0.500 | 2000K | 🧠 🔧 📎 🖼️ |
| `grok-code-fast-1` | $0.200 | $1.500 | 256K | 🧠 🔧 |
| `grok-3-mini` | $0.300 | $0.500 | 131K | 🧠 🔧 |
| `grok-3-mini-beta` | $0.300 | $0.500 | 131K | 🧠 🔧 |
| `grok-3` | $3.000 | $15.000 | 131K | 🔧 |
| `grok-3-beta` | $3.000 | $15.000 | 131K | 🔧 |
| `grok-4` | $3.000 | $15.000 | 256K | 🧠 🔧 📎 🖼️ |

### ALLENAI (7 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `olmo-2-0325-32b-instruct` | $0.050 | $0.200 | 128K | - |
| `olmo-3-7b-instruct` | $0.100 | $0.200 | 65K | - |
| `olmo-3-7b-think` | $0.120 | $0.200 | 65K | 🧠 |
| `olmo-3-32b-think` | $0.150 | $0.500 | 65K | 🧠 |
| `olmo-3.1-32b-think` | $0.150 | $0.500 | 65K | 🧠 |
| `molmo-2-8b` | $0.200 | $0.200 | 36K | 📎 🖼️ |
| `olmo-3.1-32b-instruct` | $0.200 | $0.600 | 65K | 🔧 |

### MINIMAX (7 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `minimax-m2.5:free` | $0.000 | $0.000 | 204K | 🧠 🔧 |
| `minimax-01` | $0.200 | $1.100 | 1000K | 📎 🖼️ |
| `minimax-m2` | $0.255 | $1.000 | 196K | 🧠 🔧 |
| `minimax-m2.1` | $0.270 | $0.950 | 196K | 🧠 🔧 |
| `minimax-m2.5` | $0.295 | $1.200 | 196K | 🧠 🔧 |
| `minimax-m2-her` | $0.300 | $1.200 | 65K | - |
| `minimax-m1` | $0.400 | $2.200 | 1000K | 🧠 🔧 |

### ARCEE-AI (6 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `trinity-large-preview:free` | $0.000 | $0.000 | 131K | 🔧 |
| `trinity-mini` | $0.045 | $0.150 | 131K | 🧠 🔧 |
| `spotlight` | $0.180 | $0.180 | 131K | 📎 🖼️ |
| `coder-large` | $0.500 | $0.800 | 32K | - |
| `virtuoso-large` | $0.750 | $1.200 | 131K | 🔧 |
| `maestro-reasoning` | $0.900 | $3.300 | 131K | - |

### AMAZON (5 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `nova-micro-v1` | $0.035 | $0.140 | 128K | 🔧 |
| `nova-lite-v1` | $0.060 | $0.240 | 300K | 🔧 📎 🖼️ |
| `nova-2-lite-v1` | $0.300 | $2.500 | 1000K | 🧠 🔧 📎 🖼️ |
| `nova-pro-v1` | $0.800 | $3.200 | 300K | 🔧 📎 🖼️ |
| `nova-premier-v1` | $2.500 | $12.500 | 1000K | 🔧 📎 🖼️ |

### BAIDU (5 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `ernie-4.5-21b-a3b` | $0.070 | $0.280 | 120K | 🔧 |
| `ernie-4.5-21b-a3b-thinking` | $0.070 | $0.280 | 131K | 🧠 |
| `ernie-4.5-vl-28b-a3b` | $0.140 | $0.560 | 30K | 🧠 🔧 📎 🖼️ |
| `ernie-4.5-300b-a47b` | $0.280 | $1.100 | 123K | - |
| `ernie-4.5-vl-424b-a47b` | $0.420 | $1.250 | 123K | 🧠 📎 🖼️ |

### MOONSHOTAI (5 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `kimi-k2-0905` | $0.400 | $2.000 | 131K | 🔧 |
| `kimi-k2.5` | $0.450 | $2.200 | 262K | 🧠 🔧 📎 🖼️ |
| `kimi-k2-thinking` | $0.470 | $2.000 | 131K | 🧠 🔧 |
| `kimi-k2` | $0.550 | $2.200 | 131K | 🔧 |
| `kimi-k2-0905:exacto` | $0.600 | $2.500 | 262K | 🔧 |

### NOUSRESEARCH (5 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `hermes-4-70b` | $0.130 | $0.400 | 131K | 🧠 |
| `hermes-2-pro-llama-3-8b` | $0.140 | $0.140 | 8K | - |
| `hermes-3-llama-3.1-70b` | $0.300 | $0.300 | 65K | - |
| `hermes-3-llama-3.1-405b` | $1.000 | $1.000 | 131K | - |
| `hermes-4-405b` | $1.000 | $3.000 | 131K | 🧠 |

### NVIDIA (5 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `nemotron-nano-9b-v2` | $0.040 | $0.160 | 131K | 🧠 🔧 |
| `nemotron-3-nano-30b-a3b` | $0.050 | $0.200 | 262K | 🧠 🔧 |
| `llama-3.3-nemotron-super-49b-v1.5` | $0.100 | $0.400 | 131K | 🧠 🔧 |
| `nemotron-nano-12b-v2-vl` | $0.200 | $0.600 | 131K | 🧠 📎 🖼️ |
| `llama-3.1-nemotron-70b-instruct` | $1.200 | $1.200 | 131K | 🔧 |

### PERPLEXITY (5 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `sonar` | $1.000 | $1.000 | 127K | 📎 🖼️ |
| `sonar-deep-research` | $2.000 | $8.000 | 128K | 🧠 |
| `sonar-reasoning-pro` | $2.000 | $8.000 | 128K | 🧠 📎 🖼️ |
| `sonar-pro` | $3.000 | $15.000 | 200K | 📎 🖼️ |
| `sonar-pro-search` | $3.000 | $15.000 | 200K | 🧠 📎 🖼️ |

### SAO10K (5 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `l3-lunaris-8b` | $0.040 | $0.050 | 8K | - |
| `l3.1-euryale-70b` | $0.650 | $0.750 | 32K | 🔧 |
| `l3.3-euryale-70b` | $0.650 | $0.750 | 131K | - |
| `l3-euryale-70b` | $1.480 | $1.480 | 8K | 🔧 |
| `l3.1-70b-hanami-x1` | $3.000 | $3.000 | 16K | - |

### AION-LABS (4 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `aion-1.0-mini` | $0.700 | $1.400 | 131K | 🧠 |
| `aion-2.0` | $0.800 | $1.600 | 131K | 🧠 |
| `aion-rp-llama-3.1-8b` | $0.800 | $1.600 | 32K | - |
| `aion-1.0` | $4.000 | $8.000 | 131K | 🧠 |

### COHERE (4 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `command-r7b-12-2024` | $0.037 | $0.150 | 128K | - |
| `command-r-08-2024` | $0.150 | $0.600 | 128K | 🔧 |
| `command-a` | $2.500 | $10.000 | 256K | - |
| `command-r-plus-08-2024` | $2.500 | $10.000 | 128K | 🔧 |

### THEDRUMMER (4 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `rocinante-12b` | $0.170 | $0.430 | 32K | 🔧 |
| `cydonia-24b-v4.1` | $0.300 | $0.500 | 131K | - |
| `unslopnemo-12b` | $0.400 | $0.400 | 32K | 🔧 |
| `skyfall-36b-v2` | $0.550 | $0.800 | 32K | - |

### BYTEDANCE-SEED (3 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `seed-1.6-flash` | $0.075 | $0.300 | 262K | 🧠 🔧 📎 🖼️ |
| `seed-2.0-mini` | $0.100 | $0.400 | 262K | 🧠 🔧 📎 🖼️ |
| `seed-1.6` | $0.250 | $2.000 | 262K | 🧠 🔧 📎 🖼️ |

### OTHER (3 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `corethink:free` | $0.000 | $0.000 | 78K | 🔧 |
| `giga-potato` | $0.000 | $0.000 | 256K | 🔧 📎 🖼️ |
| `giga-potato-thinking` | $0.000 | $0.000 | 256K | 🧠 🔧 📎 🖼️ |

### INCEPTION (3 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `mercury` | $0.250 | $0.750 | 128K | 🔧 |
| `mercury-2` | $0.250 | $0.750 | 128K | 🧠 🔧 |
| `mercury-coder` | $0.250 | $0.750 | 128K | 🔧 |

### KILO-AUTO (3 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `free` | $0.000 | $0.000 | 204K | 🧠 🔧 |
| `small` | $0.050 | $0.400 | 400K | 🧠 🔧 📎 🖼️ |
| `frontier` | $5.000 | $25.000 | 1000K | 🧠 🔧 📎 🖼️ |

### KILO (3 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `auto-free` | $0.000 | $0.000 | 204K | 🧠 🔧 |
| `auto-small` | $0.050 | $0.400 | 400K | 🧠 🔧 📎 🖼️ |
| `auto` | $5.000 | $25.000 | 1000K | 🧠 🔧 📎 🖼️ |

### LIQUID (3 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `lfm-2.2-6b` | $0.010 | $0.020 | 32K | - |
| `lfm2-8b-a1b` | $0.010 | $0.020 | 32K | - |
| `lfm-2-24b-a2b` | $0.030 | $0.120 | 32K | - |

### INFLECTION (2 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `inflection-3-pi` | $2.500 | $10.000 | 8K | - |
| `inflection-3-productivity` | $2.500 | $10.000 | 8K | - |

### MICROSOFT (2 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `phi-4` | $0.060 | $0.140 | 16K | - |
| `wizardlm-2-8x22b` | $0.620 | $0.620 | 65K | - |

### MORPH (2 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `morph-v3-fast` | $0.800 | $1.200 | 81K | - |
| `morph-v3-large` | $0.900 | $1.900 | 262K | - |

### NEVERSLEEP (2 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `llama-3.1-lumimaid-8b` | $0.090 | $0.600 | 32K | - |
| `noromaid-20b` | $1.000 | $1.750 | 4K | - |

### OPENROUTER (2 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `bodybuilder` | $-1000000.000 | $-1000000.000 | 128K | - |
| `free` | $0.000 | $0.000 | 200K | 🧠 🔧 📎 🖼️ |

### RELACE (2 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `relace-apply-3` | $0.850 | $1.250 | 256K | - |
| `relace-search` | $1.000 | $3.000 | 256K | 🔧 |

### STEPFUN (2 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `step-3.5-flash:free` | $0.000 | $0.000 | 256K | 🧠 🔧 |
| `step-3.5-flash` | $0.100 | $0.300 | 256K | 🧠 🔧 |

### AI21 (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `jamba-large-1.7` | $2.000 | $8.000 | 256K | 🔧 |

### ALFREDPROS (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `codellama-7b-instruct-solidity` | $0.800 | $1.200 | 4K | - |

### ALIBABA (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `tongyi-deepresearch-30b-a3b` | $0.090 | $0.450 | 131K | 🧠 🔧 |

### ALPINDALE (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `goliath-120b` | $3.750 | $7.500 | 6K | - |

### ANTHRACITE-ORG (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `magnum-v4-72b` | $3.000 | $5.000 | 16K | - |

### BYTEDANCE (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `ui-tars-1.5-7b` | $0.100 | $0.200 | 128K | 📎 🖼️ |

### DEEPCOGITO (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `cogito-v2.1-671b` | $1.250 | $1.250 | 128K | 🧠 |

### ELEUTHERAI (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `llemma_7b` | $0.800 | $1.200 | 4K | - |

### ESSENTIALAI (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `rnj-1-instruct` | $0.150 | $0.150 | 32K | 🔧 |

### GRYPHE (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `mythomax-l2-13b` | $0.060 | $0.060 | 4K | - |

### IBM-GRANITE (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `granite-4.0-h-micro` | $0.017 | $0.110 | 131K | - |

### KWAIPILOT (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `kat-coder-pro` | $0.207 | $0.828 | 256K | 🔧 |

### MANCER (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `weaver` | $0.750 | $1.000 | 8K | - |

### MEITUAN (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `longcat-flash-chat` | $0.200 | $0.800 | 131K | 🔧 |

### NEX-AGI (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `deepseek-v3.1-nex-n1` | $0.270 | $1.000 | 131K | 🔧 |

### PRIME-INTELLECT (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `intellect-3` | $0.200 | $1.100 | 131K | 🧠 🔧 |

### RAIFLE (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `sorcererlm-8x22b` | $4.500 | $4.500 | 16K | - |

### SWITCHPOINT (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `router` | $0.850 | $3.400 | 131K | 🧠 |

### TENCENT (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `hunyuan-a13b-instruct` | $0.140 | $0.570 | 131K | 🧠 |

### TNGTECH (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `deepseek-r1t2-chimera` | $0.250 | $0.850 | 163K | 🧠 🔧 |

### UNDI95 (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `remm-slerp-l2-13b` | $0.450 | $0.650 | 6K | - |

### UPSTAGE (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `solar-pro-3` | $0.150 | $0.600 | 128K | 🧠 🔧 |

### WRITER (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `palmyra-x5` | $0.600 | $6.000 | 1040K | - |

### XIAOMI (1 models)

| Model | Input/1M | Output/1M | Context | Capabilities |
|-------|----------|-----------|---------|-------------|
| `mimo-v2-flash` | $0.090 | $0.290 | 262K | 🧠 🔧 |

---

## OpenAI GPT-5.x Family (Detailed)

The GPT-5 series represents OpenAI's latest frontier models with unified Codex and GPT capabilities.

### GPT-5.4 Series (Latest - March 2026)

| Model | Description | Context | Pricing |
|-------|-------------|---------|---------|
| **gpt-5.4** | Unified Codex+GPT, 1M+ context | 1,050K | $2.50/$15.00 |
| **gpt-5.4-pro** | Mission-critical reasoning | 1,050K | $30.00/$180.00 |

**Key Features:**
- 1M+ token context window (922K input, 128K output)
- Text and image input support
- Optimized for agentic coding and long-context workflows
- Improved instruction following and tool use

### GPT-5.3 Series

| Model | Description | Context | Pricing |
|-------|-------------|---------|---------|
| **gpt-5.3-codex** | Agentic coding | 400K | $1.75/$14.00 |
| **gpt-5.3-chat** | Conversational | 128K | $1.75/$14.00 |

### GPT-5.2 Series

| Model | Description | Context | Pricing |
|-------|-------------|---------|---------|
| **gpt-5.2** | General purpose | 400K | $1.75/$14.00 |
| **gpt-5.2-codex** | Code generation | 400K | $1.75/$14.00 |
| **gpt-5.2-chat** | Conversational | 128K | $1.75/$14.00 |
| **gpt-5.2-pro** | Extended reasoning (Apex) | 400K | $21.00/$168.00 |

### GPT-5.1 Series

| Model | Description | Context | Pricing |
|-------|-------------|---------|---------|
| **gpt-5.1** | Adaptive reasoning | 400K | $1.25/$10.00 |
| **gpt-5.1-codex** | Agentic coding | 400K | $1.25/$10.00 |
| **gpt-5.1-codex-max** | Extended coding sessions | 400K | $1.25/$10.00 |
| **gpt-5.1-codex-mini** | Efficient coding | 400K | $0.25/$2.00 |
| **gpt-5.1-chat** | Fast conversational | 128K | $1.25/$10.00 |

### GPT-5 Base Series

| Model | Description | Context | Pricing |
|-------|-------------|---------|---------|
| **gpt-5** | Foundation model | 400K | $1.25/$10.00 |
| **gpt-5-codex** | Code generation | 400K | $1.25/$10.00 |
| **gpt-5-chat** | Conversational | 128K | $1.25/$10.00 |
| **gpt-5-mini** | Lightweight | 400K | $0.25/$2.00 |
| **gpt-5-nano** | Ultra-efficient | 400K | $0.05/$0.40 |
| **gpt-5-pro** | Deep reasoning (Apex) | 400K | $15.00/$120.00 |

---

## Anthropic Claude Family (Detailed)

### Claude 4.x Series

| Model | Tier | Pricing | Best For |
|-------|------|---------|----------|
| **claude-opus-4.6** | Expert | $5.00/$25.00 | Complex analysis, architecture |
| **claude-opus-4.5** | Expert | $5.00/$25.00 | Deep reasoning tasks |
| **claude-sonnet-4.6** | Expert | $3.00/$15.00 | Production code review |
| **claude-sonnet-4.5** | Expert | $3.00/$15.00 | Code generation |
| **claude-haiku-4.5** | Pro | $1.00/$5.00 | Fast inference |

### Claude 3.x Series

| Model | Tier | Pricing | Best For |
|-------|------|---------|----------|
| **claude-3.7-sonnet** | Expert | $3.00/$15.00 | Balanced tasks |
| **claude-3.7-sonnet:thinking** | Expert | $3.50/$17.50 | Extended reasoning |
| **claude-3.5-haiku** | Standard | $0.80/$4.00 | Quick tasks |
| **claude-3-haiku** | Economy | $0.25/$1.25 | Budget-friendly |

---

## Google Gemini Family (Detailed)

### Gemini 3.x Series

| Model | Description | Pricing |
|-------|-------------|---------|
| **gemini-3-flash-preview** | Fast, economical | $0.005/$0.015 |
| **gemini-3.1-pro-preview** | Production quality | $2.00/$12.00 |
| **gemini-3.1-flash-lite-preview** | Ultra-efficient | $0.25/$1.50 |

### Gemini 2.x Series

| Model | Description | Pricing |
|-------|-------------|---------|
| **gemini-2.5-pro** | Full capability | $2.50/$15.00 |
| **gemini-2.5-flash** | Fast inference | $0.007/$0.021 |
| **gemini-2.5-flash-lite** | Budget option | $0.10/$0.40 |
| **gemini-2.0-flash-001** | Legacy fast | $0.10/$0.40 |

---

## OpenAI Reasoning Models (o-series)

| Model | Description | Pricing | Use Case |
|-------|-------------|---------|----------|
| **o4-mini** | Fast reasoning | $1.10/$4.40 | Quick analysis |
| **o4-mini-high** | Enhanced reasoning | $1.10/$4.40 | Complex problems |
| **o3-mini** | Compact reasoning | $1.10/$4.40 | Balanced |
| **o3-mini-high** | Extended o3 | $10.00/$40.00 | Deep analysis |
| **o3-pro** | Maximum reasoning | $40.00/$160.00 | Mission-critical |
| **o1-pro** | Original reasoning | $35.00/$140.00 | Complex tasks |

---

## Free Tier Models

These models have zero cost and are ideal for prototyping:

| Model | Provider | Best For |
|-------|----------|----------|
| **deepseek-r1** | DeepSeek | o1-level performance |
| **minimax-m2.1** | Minimax | General purpose |
| **glm-4.7-free** | Z-AI | Multilingual |
| **kimi-k2.5:free** | MoonShot | Agentic tasks |
| **qwen3-coder** | Qwen | Code generation |
| **trinity-large-preview:free** | Arcee | Strong capabilities |

---

## Traycer Agent Mapping

Agents in `~/.traycer/cli-agents/` map to these tiers:

| Agent Prefix | Tier | Cost Range |
|--------------|------|------------|
| `Free##` | Free | $0.00 |
| `Economy##` | Economy | $0.001-0.10 |
| `Standard##` | Standard | $0.10-0.50 |
| `Pro##` | Pro | $0.50-3.00 |
| `Expert##` | Expert | $3.00-10.00 |
| `Apex##` | Apex | $15.00+ |
| `Specialist##` | Specialist | Varies (Codestral) |

**Total Agents:** 55 (as of 2026-03-09)

---

## See Also

- [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md) - Task-based selection
- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) - CLI commands
- [TRAYCER-KILO-AGENTS-GUIDE.md](../../traycer/TRAYCER-KILO-AGENTS-GUIDE.md) - Traycer integration
