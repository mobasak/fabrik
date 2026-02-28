# AI Client

**Last Updated:** 2026-02-28

**Purpose:** Provider-agnostic LLM client used by `fabrik ai` CLI commands.

## Usage

```bash
fabrik ai generate --provider claude "Draft a release note for Phase 6"
fabrik ai revise "Original text" "Make it shorter"
```

## Configuration

- `ANTHROPIC_API_KEY` for Claude requests
- `OPENAI_API_KEY` for OpenAI requests

## See also

- [CONFIGURATION.md](../CONFIGURATION.md)
- [SERVICES.md](../SERVICES.md)
