---
activation: glob
globs: ["**/code-assist/**", "**/copilot/**", "**/codegen/**", "**/code-gen/**", "**/code-review-ai/**"]
description: Code & Developer AI (category 6) — code AI embedded in a product (generate, edit, explain, review code). Code-writing features run on Claude through claude -p on ai/50's agent loop, with the code run in a container or VM and repository content treated as untrusted input. Fabrik's own development runs on Claude Code in VS Code.
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: Coding agents building a product feature that writes, edits, explains or reviews code
     GOAL: Run the feature on ai/50's Claude loop, isolate the code it runs, and treat the repository as untrusted input.
     AGENT USAGE: This pack is about code AI inside a product, not the tooling Fabrik is developed with. Model choice
     across categories is ai/00-ai-model-selection.md; record a project's choice and the rejected alternative in
     project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`), as ai/00's selection workflow says. -->

# 6. Code & Developer AI

Last content verification: 2026-10-02

**Purpose:** Generate or explain code.

## Fabrik defaults

- **Fabrik's own development** runs on Claude Code: the VS Code extension and the CLI, on the Max subscription
  (operator ruling, D-514). Windsurf is no longer used (D-514), nor is the Kilo CLI (D-364). OpenRouter agents are a
  possible later option (D-514); the metered subagent pool they would use is paused by ruling (D-181/D-182).
- **Code-writing features → Claude through `claude -p`** on the agent loop ai/50-agentic.md sets: fabrik-lib's
  `llm-dispatch` `run_agentic` on `opus`, with its bounds, its auth rules and its interim rule for features that answer
  other users' requests. Under the loop's `dontAsk` mode a tool that would prompt is denied, so restrict the set with
  `tools` and grant editing and commands with `allowed_tools` (`Edit`, a `Bash` rule scoped to a command prefix).
  `scripts/ci_fix_dispatcher.py`, which runs `claude -p` on the host with permissions skipped to fix a failing CI run,
  is the operator's own automation over the operator's own repositories; it predates these rules and is not the pattern
  for a product feature.
- **Never run generated code on the host.** Claude Code's sandboxed Bash tool limits files and network for Bash commands
  and their children, but its file tools, MCP servers and hooks still run on the host, so on its own it does not
  contain an unattended agent. Run an unattended code agent inside a container, a VM, or Anthropic's sandbox runtime
  (a research preview that wraps the whole process on the host), with network egress closed or allow-listed, because
  any open egress can leak what the agent can read; code from an untrusted repository, such as another user's, goes in
  a dedicated VM (a hosted sandbox, § Subcategories). Where the Bash sandbox is used, set `sandbox.failIfUnavailable`:
  without it, a sandbox that cannot start lets commands run unsandboxed.
- **The repository is untrusted input.** OWASP puts prompt injection first among the risks of LLM applications and
  names repository code, issue titles, package READMEs and changelogs, and tool output as places it comes from — a
  poisoned issue has made a coding assistant leak private repositories, and a runtime injection has made an IDE agent
  execute arbitrary code. Its "Rule of Two" gives the floor: an agent that reads untrusted input, can reach sensitive
  data and can change state needs a human to approve each action. A code-writing feature is all three, so keep
  credentials out of the agent's reach, give it the least privilege the task needs, and have a human approve the exact
  change before anything with side effects — a push, a deploy, a migration — runs; a read-only review escapes the rule
  because it changes nothing. A headless run skips Claude Code's trust check and, outside bare mode, loads the
  project's hooks and `.mcp.json`; keep the loop's default `setting_sources=""` and pass `strict_mcp_config=True` with
  any `mcp_configs` (ai/50).
- **Code review.** Fleet repositories review through the /fabrik-review family (core/50-code-review.md). A product's
  review feature runs on the same Claude loop, read-only (Read, Grep, Glob), with its findings returned as structured
  output.

**Licence trap — open code models carry their own terms.** Mistral's open Codestral weights are under its non-production
licence (testing, research and evaluation only; no commercial or hosted use), and its current Codestral is API-only.
Mistral's open coding model ships under a modified MIT licence with a revenue cap, and Qwen's newer licences gate
commercial "AI work assistant" products, which includes coding tools. Older DeepSeek releases split a permissive code
licence from a stricter weights licence. Read the licence file of the exact weights.

## Subcategories

- **Developer tools** (for reference; not Fabrik's stack): GitHub Copilot and its cloud agent; Cursor, owned by SpaceX;
  Windsurf, now Cognition's Devin Desktop; Amazon Q Developer, whose IDE plugins give way to Kiro; OpenAI Codex (its
  CLI is Apache-licensed); Google's Antigravity CLI, which replaced Gemini CLI for consumers; Google Jules.
- **Open code models** (hosted first, a GPU pod only past core/76-gpu-workers.md's break-even): Qwen's coder line
  (Apache-licensed, hosted on OpenRouter), DeepSeek's open models (MIT), OpenAI's gpt-oss (Apache). Mistral's Devstral
  is retired on its API.
- **Hosted sandboxes for generated code:** E2B (Firecracker microVMs), Daytona (containers by default, a VM class),
  Modal (gVisor; outbound network open until you block it). All bill per second.
- **Review products:** Claude Code's `/code-review` reviews a diff locally on the Max plan and posts to the PR with
  `--comment` (its hosted PR-review service is Team and Enterprise only); GitHub Copilot code review; CodeRabbit;
  Graphite, now owned by Cursor. Claude Code's GitHub action (`anthropics/claude-code-action`) authenticates only by
  API key or a static subscription token, both outside the fleet's auth boundary (ai/00, ai/50), so it is reference only.
- **Compare on:** Terminal-Bench, which is current; Scale's SWE-Bench Pro board, which lags the vendor-reported scores.
  SWE-bench Verified is saturated and mostly self-reported, and LiveCodeBench and Aider's polyglot board have not been
  updated in months.

## Gateway coverage

For a non-Claude code model, OpenRouter lists coding models under its programming category, a curated list that leaves
some out, and its programming ranking orders models by tokens processed — usage, not quality. Pick the model and rate
from the bake-off browser's Coding tab (hub-only).

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-07 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-07 UTC; auto-refreshed from `kilo_agents.db`):*

code-tagged across all gateways: **0**

See the Coding tab in the bake-off browser; sort by Best Code descending to compare SWE-bench + Aider + DA-code signals per row.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** code completion, refactoring, debugging assistance.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-07 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-07 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='code' floors: min_quality_tier=2, min_context_window_k=64, require_vision=False, require_tools=True, require_reasoning=False, allow_free=True, stability_required=False, sort_key='tbench_accuracy DESC'*
<!-- OPENROUTER_ROUTES:END -->
