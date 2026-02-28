# Kilo AI System Documentation

**Last Updated:** 2026-02-28

**Status:** Complete model extraction, partial pricing verification

## Core Concepts

**Models:** 319 AI models from 57 providers

**Agents:** Pre-configured model + variant + system prompt combinations

**Variants:** Reasoning effort levels: minimal, low, medium, high, max

**Sessions:** Conversation history management

**MCP/ACP:** Model Context Protocol and Agent Client Protocol support

## Model System

**Total Models:** 319

**Providers:** 57

**With Verified Pricing:** 16

### Categories

- **Coding Specialists:** 20
- **Vision Models:** 17
- **Thinking/Reasoning:** 20
- **Fast (Flash):** 14
- **Budget (Mini):** 41
- **Premium (Pro):** 17
- **Claude Opus:** 4
- **Claude Sonnet:** 6
- **Claude Haiku:** 3

## Variants

**Description:** Reasoning effort control parameter

### Options

- minimal
- low
- medium
- high
- max

**Usage:** --variant high

**Effect:** Higher = more thinking tokens, better quality, higher cost

## Pricing

**Unit:** Per 10M tokens (input + output combined for simplicity)

**Verified Sources:** Kilo cache (.model_update_cache.json)

**Range:** $0.12 - $12.00 per 10M tokens

**Ultra Budget:** $0.12 - $0.20/10M

**Budget:** $0.25 - $0.50/10M

**Mid-Tier:** $0.60 - $2.00/10M

**Premium:** $2.00 - $12.00/10M

## Cli Commands

**kilo models:** List all available models

**kilo models --verbose:** Show detailed model info with costs

**kilo run:** Interactive chat

**kilo agent:** Manage agents

**kilo stats:** Show token usage and costs

**kilo session:** Manage conversation sessions

**kilo mcp:** Model Context Protocol server management

**kilo web:** Web interface

## File Locations

**Agents:** ~/.traycer/cli-agents/

**Model Cache:** /opt/fabrik/scripts/.model_update_cache.json

**All Models:** /opt/fabrik/scripts/kilo_all_models.json

**Comprehensive DB:** /opt/fabrik/scripts/kilo_comprehensive_db.json

**Sessions:** ~/.traycer/sessions/

## Data Files Created

**kilo_all_models.json:** Complete catalog of 319 models

**kilo_comprehensive_db.json:** Models with variants, pricing, capabilities

**.model_update_cache.json:** Verified pricing for 16 models

**kilo_pricing_comprehensive.json:** Extended pricing (verified + estimated)

**kilo_streamlined_stack.json:** 8 verified agents for implementation

