# CLI Reference

> Complete reference for droid command-line interface, including commands and flags

## Installation

<CodeGroup>
  ```bash macOS/Linux theme={null}
  curl -fsSL https://app.factory.ai/cli | sh
  ```

  ```powershell Windows theme={null}
  irm https://app.factory.ai/cli/windows | iex
  ```
</CodeGroup>

The CLI operates in two modes:

* **Interactive (`droid`)** - Chat-first REPL with slash commands
* **Non-interactive (`droid exec`)** - Single-shot execution for automation and scripting

## CLI commands

| Command                      | Description                           | Example                                        |
| :--------------------------- | :------------------------------------ | :--------------------------------------------- |
| `droid`                      | Start interactive REPL                | `droid`                                        |
| `droid "query"`              | Start REPL with initial prompt        | `droid "explain this project"`                 |
| `droid exec "query"`         | Execute task without interactive mode | `droid exec "summarize src/auth"`              |
| `droid exec -f prompt.md`    | Load prompt from file                 | `droid exec -f .factory/prompts/review.md`     |
| `cat file \| droid exec`     | Process piped content                 | `git diff \| droid exec "draft release notes"` |
| `droid exec -s <id> "query"` | Resume existing session in exec mode  | `droid exec -s session-123 "continue"`         |
| `droid exec --list-tools`    | List available tools, then exit       | `droid exec --list-tools`                      |

## CLI flags

Customize droid's behavior with command-line flags:

| Flag                              | Description                                                        | Example                                                      |
| :-------------------------------- | :----------------------------------------------------------------- | :----------------------------------------------------------- |
| `-f, --file <path>`               | Read prompt from a file                                            | `droid exec -f plan.md`                                      |
| `-m, --model <id>`                | Select a specific model (see [model IDs](#available-models))       | `droid exec -m claude-opus-4-5-20251101`                     |
| `-s, --session-id <id>`           | Continue an existing session                                       | `droid exec -s session-abc123`                               |
| `--auto <level>`                  | Set [autonomy level](#autonomy-levels) (`low`, `medium`, `high`)   | `droid exec --auto medium "run tests"`                       |
| `--enabled-tools <ids>`           | Force-enable specific tools (comma or space separated)             | `droid exec --enabled-tools ApplyPatch,Bash`                 |
| `--disabled-tools <ids>`          | Disable specific tools for this run                                | `droid exec --disabled-tools execute-cli`                    |
| `--list-tools`                    | Print available tools and exit                                     | `droid exec --list-tools`                                    |
| `-o, --output-format <format>`    | Output format (`text`, `json`, `stream-json`, `stream-jsonrpc`)    | `droid exec -o json "document API"`                          |
| `--input-format <format>`         | Input format (`stream-json`, `stream-jsonrpc` for multi-turn)      | `droid exec --input-format stream-jsonrpc -o stream-jsonrpc` |
| `-r, --reasoning-effort <level>`  | Override reasoning effort (`off`, `none`, `low`, `medium`, `high`) | `droid exec -r high "debug flaky test"`                      |
| `--spec-model <id>`               | Use a different model for specification planning                   | `droid exec --spec-model claude-sonnet-4-5-20250929`         |
| `--spec-reasoning-effort <level>` | Override reasoning effort for spec mode                            | `droid exec --use-spec --spec-reasoning-effort high`         |
| `--use-spec`                      | Start in specification mode (plan before executing)                | `droid exec --use-spec "add user profiles"`                  |
| `--skip-permissions-unsafe`       | Skip all permission prompts (⚠️ use with extreme caution)          | `droid exec --skip-permissions-unsafe`                       |
| `--cwd <path>`                    | Execute from a specific working directory                          | `droid exec --cwd ../service "run tests"`                    |
| `--delegation-url <url>`          | URL for delegated sessions (Slack thread or Linear issue)          | `droid exec --delegation-url <slack-or-linear-url>`          |
| `-v, --version`                   | Display CLI version                                                | `droid -v`                                                   |
| `-h, --help`                      | Show help information                                              | `droid --help`                                               |

<Tip>
  Use `--output-format json` for scripting and automation, allowing you to parse droid's responses programmatically.
</Tip>

## Autonomy levels

`droid exec` uses tiered autonomy to control what operations the agent can perform. Only raise access when the environment is safe.

| Level                       | Intended for             | Notable allowances                                            |
| :-------------------------- | :----------------------- | :------------------------------------------------------------ |
| *(default)*                 | Read-only reconnaissance | File reads, git diffs, environment inspection                 |
| `--auto low`                | Safe edits               | Create/edit files, run formatters, non-destructive commands   |
| `--auto medium`             | Local development        | Install dependencies, build/test, local git commits           |
| `--auto high`               | CI/CD & orchestration    | Git push, deploy scripts, long-running operations             |
| `--skip-permissions-unsafe` | Isolated sandboxes only  | Removes all guardrails (⚠️ use only in disposable containers) |

**Examples:**

```bash  theme={null}
# Default (read-only)
droid exec "Analyze the auth system and create a plan"

# Low autonomy - safe edits
droid exec --auto low "Add JSDoc comments to all functions"

# Medium autonomy - development work
droid exec --auto medium "Install deps, run tests, fix issues"

# High autonomy - deployment
droid exec --auto high "Run tests, commit, and push changes"
```

<Warning>
  `--skip-permissions-unsafe` removes all safety checks. Use **only** in isolated environments like Docker containers.
</Warning>

## Available models

| Model ID                     | Name                      | Reasoning support                | Default reasoning |
| :--------------------------- | :------------------------ | :------------------------------- | :---------------- |
| `claude-opus-4-5-20251101`   | Claude Opus 4.5 (default) | Yes (Off/Low/Medium/High)        | off               |
| `gpt-5.1-codex-max`          | GPT-5.1-Codex-Max         | Yes (Low/Medium/High/Extra High) | medium            |
| `gpt-5.1-codex`              | GPT-5.1-Codex             | Yes (Low/Medium/High)            | medium            |
| `gpt-5.1`                    | GPT-5.1                   | Yes (None/Low/Medium/High)       | none              |
| `gpt-5.2`                    | GPT-5.2                   | Yes (Low/Medium/High)            | low               |
| `claude-sonnet-4-5-20250929` | Claude Sonnet 4.5         | Yes (Off/Low/Medium/High)        | off               |
| `claude-haiku-4-5-20251001`  | Claude Haiku 4.5          | Yes (Off/Low/Medium/High)        | off               |
| `gemini-3-pro-preview`       | Gemini 3 Pro              | Yes (Low/High)                   | high              |
| `gemini-3-flash-preview`     | Gemini 3 Flash            | Yes (Minimal/Low/Medium/High)    | high              |
| `glm-4.6`                    | Droid Core (GLM-4.6)      | None only                        | none              |

Custom models configured via [BYOK](/cli/configuration/byok) use the format: `custom:<alias>`

See [Choosing Your Model](/cli/user-guides/choosing-your-model) for detailed guidance on which model to use for different tasks.

## Interactive mode features

### Bash mode

Press `!` when the input is empty to toggle bash mode. In bash mode, commands execute directly in your shell without AI interpretation—useful for quick operations like checking `git status` or running `npm test`.

* **Toggle on:** Press `!` (when input is empty)
* **Execute commands:** Type any shell command and press Enter
* **Toggle off:** Press `Esc` to return to normal AI chat mode

The prompt changes from `>` to `$` when bash mode is active.

### Slash commands

Available when running `droid` in interactive mode. Type the command at the prompt:

| Command                | Description                                       |
| :--------------------- | :------------------------------------------------ |
| `/account`             | Open Factory account settings in browser          |
| `/billing`             | View and manage billing settings                  |
| `/bug [title]`         | Create a bug report with session data and logs    |
| `/clear`               | Start a new session (alias for `/new`)            |
| `/commands`            | Manage custom slash commands                      |
| `/compress [prompt]`   | Compress session and move to new one with summary |
| `/cost`                | Show token usage statistics                       |
| `/droids`              | Manage custom droids                              |
| `/favorite`            | Mark current session as a favorite                |
| `/help`                | Show available slash commands                     |
| `/hooks`               | Manage lifecycle hooks                            |
| `/ide`                 | Configure IDE integrations                        |
| `/login`               | Sign in to Factory                                |
| `/logout`              | Sign out of Factory                               |
| `/mcp`                 | Manage Model Context Protocol servers             |
| `/model`               | Switch AI model mid-session                       |
| `/new`                 | Start a new session                               |
| `/quit`                | Exit droid (alias: `exit`, or press Ctrl+C)       |
| `/readiness-report`    | Generate readiness report                         |
| `/review`              | Start AI-powered code review workflow             |
| `/rewind-conversation` | Undo recent changes in the session                |
| `/sessions`            | List and select previous sessions                 |
| `/settings`            | Configure application settings                    |
| `/skills`              | Manage and invoke skills                          |
| `/status`              | Show current droid status and configuration       |
| `/terminal-setup`      | Configure terminal keybindings for Shift+Enter    |

For detailed information on slash commands, see the [interactive mode documentation](/cli/getting-started/quickstart#useful-slash-commands).

### MCP command reference

The `/mcp` slash command opens an interactive manager UI for browsing and managing MCP servers.

**Quick start:** Type `/mcp` and select **"Add from Registry"** to browse 40+ pre-configured servers (Linear, Sentry, Notion, Stripe, Vercel, and more). Select a server, authenticate if required, and you're ready to go.

**CLI commands** for scripting and automation:

```bash  theme={null}
droid mcp add <name> <url> --type http    # Add HTTP server
droid mcp add <name> "<command>"          # Add stdio server
droid mcp remove <name>                   # Remove a server
```

See [MCP Configuration](/cli/configuration/mcp) for the full registry list, CLI options (`--env`, `--header`), configuration files, and how user vs project config layering works.

## Authentication

1. Generate an API key at [app.factory.ai/settings/api-keys](https://app.factory.ai/settings/api-keys)
2. Set the environment variable:

<CodeGroup>
  ```bash macOS/Linux theme={null}
  export FACTORY_API_KEY=fk-...
  ```

  ```powershell Windows (PowerShell) theme={null}
  $env:FACTORY_API_KEY="fk-..."
  ```

  ```cmd Windows (CMD) theme={null}
  set FACTORY_API_KEY=fk-...
  ```
</CodeGroup>

**Persist the variable** in your shell profile (`~/.bashrc`, `~/.zshrc`, or PowerShell `$PROFILE`) for long-term use.

<Warning>
  Never commit API keys to source control. Use environment variables or secure secret management.
</Warning>

## Exit codes

| Code | Meaning                       |
| :--- | :---------------------------- |
| `0`  | Success                       |
| `1`  | General runtime error         |
| `2`  | Invalid CLI arguments/options |

## Common workflows

### Code review

```bash  theme={null}
# Interactive review workflow
> /review

# Analysis via exec (non-interactive)
droid exec "Review this PR for security issues"

# With modifications
droid exec --auto low "Review code and add missing type hints"
```

See the [Code Review documentation](/cli/features/code-review) for detailed guidance on review types, workflows, and best practices.

### Testing and debugging

```bash  theme={null}
# Investigation
droid exec "Analyze failing tests and explain root cause"

# Fix and verify
droid exec --auto medium "Fix failing tests and run test suite"
```

### Refactoring

```bash  theme={null}
# Planning
droid exec "Create refactoring plan for auth module"

# Execution
droid exec --auto low --use-spec "Refactor auth module"
```

### CI/CD integration

```yaml  theme={null}
# GitHub Actions example
- name: Run Droid Analysis
  env:
    FACTORY_API_KEY: ${{ secrets.FACTORY_API_KEY }}
  run: |
    droid exec --auto medium -f .github/prompts/deploy.md
```

## See also

* [Quickstart guide](/cli/getting-started/quickstart) - Getting started with Factory CLI
* [Interactive mode](/cli/getting-started/quickstart) - Shortcuts, input modes, and features
* [Choosing your model](/cli/user-guides/choosing-your-model) - Model selection guidance
* [Settings](/cli/configuration/settings) - Configuration options
* [Custom commands](/cli/configuration/custom-slash-commands) - Create your own shortcuts
* [Custom droids](/cli/configuration/custom-droids) - Build specialized agents
* [Droid Exec overview](/cli/droid-exec/overview) - Detailed automation guide
* [MCP configuration](/cli/configuration/mcp) - External tool integration


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Hooks reference

> Reference documentation for implementing hooks in Droid

<Tip>
  For a quickstart guide with examples, see [Get started with hooks](/cli/configuration/hooks-guide).
</Tip>

## Configuration

Droid hooks are configured in your [settings files](/cli/configuration/settings):

* `~/.factory/settings.json` - User settings
* `.factory/settings.json` - Project settings
* `.factory/settings.local.json` - Local project settings (not committed)
* Enterprise managed policy settings

### Structure

Hooks are organized by matchers, where each matcher can have multiple hooks:

```json  theme={null}
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here"
          }
        ]
      }
    ]
  }
}
```

* **matcher**: Pattern to match tool names, case-sensitive (only applicable for
  `PreToolUse` and `PostToolUse`)
  * Simple strings match exactly: `Write` matches only the Write tool
  * Supports regex: `Edit|Write` or `Notebook.*`
  * Use `*` to match all tools. You can also use empty string (`""`) or leave
    `matcher` blank.
* **hooks**: Array of commands to execute when the pattern matches
  * `type`: Currently only `"command"` is supported
  * `command`: The bash command to execute (can use `$FACTORY_PROJECT_DIR`
    environment variable)
  * `timeout`: (Optional) How long a command should run, in seconds, before
    canceling that specific command.

<Warning>
  **Always use absolute paths** for hook commands and scripts, not relative paths.
  Hooks execute from Droid's current working directory, which may change during execution.
  Use `"$FACTORY_PROJECT_DIR"/path/to/script.sh` for project-relative scripts or full paths like
  `/usr/local/bin/script.sh` or `~/.factory/hooks/script.sh` for global scripts.
</Warning>

For events like `UserPromptSubmit`, `Notification`, `Stop`, and `SubagentStop`
that don't use matchers, you can omit the matcher field:

```json  theme={null}
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/prompt-validator.py"
          }
        ]
      }
    ]
  }
}
```

### Project-Specific Hook Scripts

You can use the environment variable `FACTORY_PROJECT_DIR` (only available when
Droid spawns the hook command) to reference scripts stored in your project,
ensuring they work regardless of Droid's current directory:

```json  theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$FACTORY_PROJECT_DIR\"/.factory/hooks/check-style.sh"
          }
        ]
      }
    ]
  }
}
```

### Plugin hooks

Plugins can provide hooks that integrate seamlessly with your user and project hooks. Plugin hooks are automatically merged with your configuration when plugins are enabled.

**How plugin hooks work**:

* Plugin hooks are defined in the plugin's `hooks/hooks.json` file or in a file given by a custom path to the `hooks` field.
* When a plugin is enabled, its hooks are merged with user and project hooks
* Multiple hooks from different sources can respond to the same event
* Plugin hooks use the `${DROID_PLUGIN_ROOT}` environment variable to reference plugin files

**Example plugin hook configuration**:

```json  theme={null}
{
  "description": "Automatic code formatting",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${DROID_PLUGIN_ROOT}/scripts/format.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

<Note>
  Plugin hooks use the same format as regular hooks with an optional `description` field to explain the hook's purpose.
</Note>

<Note>
  Plugin hooks run alongside your custom hooks. If multiple hooks match an event, they all execute in parallel.
</Note>

**Environment variables for plugins**:

* `${DROID_PLUGIN_ROOT}`: Absolute path to the plugin directory
* `${FACTORY_PROJECT_DIR}`: Project root directory (same as for project hooks)
* All standard environment variables are available

See the plugin components reference for details on creating plugin hooks.

## Hook Events

### PreToolUse

Runs after Droid creates tool parameters and before processing the tool call.

**Common matchers:**

* `Task` - Sub-droid tasks (see [subagents documentation](/cli/user-guides/specification-mode))
* `Bash` - Shell commands
* `Glob` - File pattern matching
* `Grep` - Content search
* `Read` - File reading
* `Edit` - File editing
* `Write` - File writing
* `WebFetch`, `WebSearch` - Web operations

### PostToolUse

Runs immediately after a tool completes successfully.

Recognizes the same matcher values as PreToolUse.

### Notification

Runs when Droid sends notifications. Notifications are sent when:

1. Droid needs your permission to use a tool. Example: "Droid needs your
   permission to use Bash"
2. The prompt input has been idle for at least 60 seconds. "Droid is waiting
   for your input"

### UserPromptSubmit

Runs when the user submits a prompt, before Droid processes it. This allows you
to add additional context based on the prompt/conversation, validate prompts, or
block certain types of prompts.

### Stop

Runs when Droid has finished responding. Does not run if
the stoppage occurred due to a user interrupt.

### SubagentStop

Runs when a sub-droid (Task tool call) has finished responding.

### PreCompact

Runs before Droid is about to run a compact operation.

**Matchers:**

* `manual` - Invoked from `/compact`
* `auto` - Invoked from auto-compact (due to full context window)

### SessionStart

Runs when Droid starts a new session or resumes an existing session (which
currently does start a new session under the hood). Useful for loading in
development context like existing issues or recent changes to your codebase, installing dependencies, or setting up environment variables.

**Matchers:**

* `startup` - Invoked from startup
* `resume` - Invoked from `--resume`, `--continue`, or `/resume`
* `clear` - Invoked from `/clear`
* `compact` - Invoked from auto or manual compact.

### SessionEnd

Runs when a Droid session ends. Useful for cleanup tasks, logging session
statistics, or saving session state.

The `reason` field in the hook input will be one of:

* `clear` - Session cleared with /clear command
* `logout` - User logged out
* `prompt_input_exit` - User exited while prompt input was visible
* `other` - Other exit reasons

## Hook Input

Hooks receive JSON data via stdin containing session information and
event-specific data:

```typescript  theme={null}
{
  // Common fields
  session_id: string
  transcript_path: string  // Path to conversation JSON
  cwd: string              // The current working directory when the hook is invoked
  permission_mode: string  // Current permission mode: "default", "plan", "acceptEdits", or "bypassPermissions"

  // Event-specific fields
  hook_event_name: string
  ...
}
```

### PreToolUse Input

The exact schema for `tool_input` depends on the tool.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  }
}
```

### PostToolUse Input

The exact schema for `tool_input` and `tool_response` depends on the tool.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_response": {
    "filePath": "/path/to/file.txt",
    "success": true
  }
}
```

### Notification Input

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Notification",
  "message": "Task completed successfully"
}
```

### UserPromptSubmit Input

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Write a function to calculate the factorial of a number"
}
```

### Stop and SubagentStop Input

`stop_hook_active` is true when Droid is already continuing as a result of
a stop hook. Check this value or process the transcript to prevent Droid
from running indefinitely.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Stop",
  "stop_hook_active": true
}
```

### PreCompact Input

For `manual`, `custom_instructions` comes from what the user passes into
`/compact`. For `auto`, `custom_instructions` is empty.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PreCompact",
  "trigger": "manual",
  "custom_instructions": ""
}
```

### SessionStart Input

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "SessionStart",
  "source": "startup"
}
```

### SessionEnd Input

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "SessionEnd",
  "reason": "exit"
}
```

## Hook Output

There are two ways for hooks to return output back to Droid. The output
communicates whether to block and any feedback that should be shown to Droid
and the user.

### Simple: Exit Code

Hooks communicate status through exit codes, stdout, and stderr:

* **Exit code 0**: Success. `stdout` is shown to the user in transcript mode
  (CTRL-R), except for `UserPromptSubmit` and `SessionStart`, where stdout is
  added to the context.
* **Exit code 2**: Blocking error. `stderr` is fed back to Droid to process
  automatically. See per-hook-event behavior below.
* **Other exit codes**: Non-blocking error. `stderr` is shown to the user and
  execution continues.

<Warning>
  Reminder: Droid does not see stdout if the exit code is 0, except for
  the `UserPromptSubmit` hook where stdout is injected as context.
</Warning>

#### Exit Code 2 Behavior

| Hook Event         | Behavior                                                           |
| ------------------ | ------------------------------------------------------------------ |
| `PreToolUse`       | Blocks the tool call, shows stderr to Droid                        |
| `PostToolUse`      | Shows stderr to Droid (tool already ran)                           |
| `Notification`     | N/A, shows stderr to user only                                     |
| `UserPromptSubmit` | Blocks prompt processing, erases prompt, shows stderr to user only |
| `Stop`             | Blocks stoppage, shows stderr to Droid                             |
| `SubagentStop`     | Blocks stoppage, shows stderr to sub-droid                         |
| `PreCompact`       | N/A, shows stderr to user only                                     |
| `SessionStart`     | N/A, shows stderr to user only                                     |
| `SessionEnd`       | N/A, shows stderr to user only                                     |

### Advanced: JSON Output

Hooks can return structured JSON in `stdout` for more sophisticated control:

#### Common JSON Fields

All hook types can include these optional fields:

```json  theme={null}
{
  "continue": true, // Whether Droid should continue after hook execution (default: true)
  "stopReason": "string", // Message shown when continue is false

  "suppressOutput": true, // Hide stdout from transcript mode (default: false)
  "systemMessage": "string" // Optional warning message shown to the user
}
```

If `continue` is false, Droid stops processing after the hooks run.

* For `PreToolUse`, this is different from `"permissionDecision": "deny"`, which
  only blocks a specific tool call and provides automatic feedback to Droid.
* For `PostToolUse`, this is different from `"decision": "block"`, which
  provides automated feedback to Droid.
* For `UserPromptSubmit`, this prevents the prompt from being processed.
* For `Stop` and `SubagentStop`, this takes precedence over any
  `"decision": "block"` output.
* In all cases, `"continue" = false` takes precedence over any
  `"decision": "block"` output.

`stopReason` accompanies `continue` with a reason shown to the user, not shown
to Droid.

#### `PreToolUse` Decision Control

`PreToolUse` hooks can control whether a tool call proceeds.

* `"allow"` bypasses the permission system. `permissionDecisionReason` is shown
  to the user but not to Droid.
* `"deny"` prevents the tool call from executing. `permissionDecisionReason` is
  shown to Droid.
* `"ask"` asks the user to confirm the tool call in the UI.
  `permissionDecisionReason` is shown to the user but not to Droid.

Additionally, hooks can modify tool inputs before execution using `updatedInput`:

* `updatedInput` allows you to modify the tool's input parameters before the tool executes. This is a `Record<string, unknown>` object containing the fields you want to change or add.
* This is most useful with `"permissionDecision": "allow"` to modify and approve tool calls.

```json  theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "My reason here",
    "updatedInput": {
      "field_to_modify": "new value"
    }
  }
}
```

<Note>
  The `decision` and `reason` fields are deprecated for PreToolUse hooks.
  Use `hookSpecificOutput.permissionDecision` and
  `hookSpecificOutput.permissionDecisionReason` instead. The deprecated fields
  `"approve"` and `"block"` map to `"allow"` and `"deny"` respectively.
</Note>

#### `PostToolUse` Decision Control

`PostToolUse` hooks can provide feedback to Droid after tool execution.

* `"block"` automatically prompts Droid with `reason`.
* `undefined` does nothing. `reason` is ignored.
* `"hookSpecificOutput.additionalContext"` adds context for Droid to consider.

```json  theme={null}
{
  "decision": "block" | undefined,
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Additional information for Droid"
  }
}
```

#### `UserPromptSubmit` Decision Control

`UserPromptSubmit` hooks can control whether a user prompt is processed.

* `"block"` prevents the prompt from being processed. The submitted prompt is
  erased from context. `"reason"` is shown to the user but not added to context.
* `undefined` allows the prompt to proceed normally. `"reason"` is ignored.
* `"hookSpecificOutput.additionalContext"` adds the string to the context if not
  blocked.

```json  theme={null}
{
  "decision": "block" | undefined,
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "My additional context here"
  }
}
```

#### `Stop`/`SubagentStop` Decision Control

`Stop` and `SubagentStop` hooks can control whether Droid must continue.

* `"block"` prevents Droid from stopping. You must populate `reason` for Droid
  to know how to proceed.
* `undefined` allows Droid to stop. `reason` is ignored.

```json  theme={null}
{
  "decision": "block" | undefined,
  "reason": "Must be provided when Droid is blocked from stopping"
}
```

#### `SessionStart` Decision Control

`SessionStart` hooks allow you to load in context at the start of a session.

* `"hookSpecificOutput.additionalContext"` adds the string to the context.
* Multiple hooks' `additionalContext` values are concatenated.

```json  theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "My additional context here"
  }
}
```

#### `SessionEnd` Decision Control

`SessionEnd` hooks run when a session ends. They cannot block session termination
but can perform cleanup tasks.

#### Exit Code Example: Bash Command Validation

```python  theme={null}
#!/usr/bin/env python3
import json
import re
import sys

# Define validation rules as a list of (regex pattern, message) tuples
VALIDATION_RULES = [
    (
        r"\bgrep\b(?!.*\|)",
        "Use 'rg' (ripgrep) instead of 'grep' for better performance and features",
    ),
    (
        r"\bfind\s+\S+\s+-name\b",
        "Use 'rg --files | rg pattern' or 'rg --files -g pattern' instead of 'find -name' for better performance",
    ),
]


def validate_command(command: str) -> list[str]:
    issues = []
    for pattern, message in VALIDATION_RULES:
        if re.search(pattern, command):
            issues.append(message)
    return issues


try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
command = tool_input.get("command", "")

if tool_name != "Bash" or not command:
    sys.exit(1)

# Validate the command
issues = validate_command(command)

if issues:
    for message in issues:
        print(f"• {message}", file=sys.stderr)
    # Exit code 2 blocks tool call and shows stderr to Droid
    sys.exit(2)
```

#### JSON Output Example: UserPromptSubmit to Add Context and Validation

<Note>
  For `UserPromptSubmit` hooks, you can inject context using either method:

  * Exit code 0 with stdout: Droid sees the context (special case for `UserPromptSubmit`)
  * JSON output: Provides more control over the behavior
</Note>

```python  theme={null}
#!/usr/bin/env python3
import json
import sys
import re
import datetime

# Load input from stdin
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

prompt = input_data.get("prompt", "")

# Check for sensitive patterns
sensitive_patterns = [
    (r"(?i)\b(password|secret|key|token)\s*[:=]", "Prompt contains potential secrets"),
]

for pattern, message in sensitive_patterns:
    if re.search(pattern, prompt):
        # Use JSON output to block with a specific reason
        output = {
            "decision": "block",
            "reason": f"Security policy violation: {message}. Please rephrase your request without sensitive information."
        }
        print(json.dumps(output))
        sys.exit(0)

# Add current time to context
context = f"Current time: {datetime.datetime.now()}"
print(context)

"""
The following is also equivalent:
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": context,
  },
}))
"""

# Allow the prompt to proceed with the additional context
sys.exit(0)
```

#### JSON Output Example: PreToolUse with Approval

```python  theme={null}
#!/usr/bin/env python3
import json
import sys

# Load input from stdin
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})

# Example: Auto-approve file reads for documentation files
if tool_name == "Read":
    file_path = tool_input.get("file_path", "")
    if file_path.endswith((".md", ".mdx", ".txt", ".json")):
        # Use JSON output to auto-approve the tool call
        output = {
            "decision": "approve",
            "reason": "Documentation file auto-approved",
            "suppressOutput": True  # Don't show in transcript mode
        }
        print(json.dumps(output))
        sys.exit(0)

# For other cases, let the normal permission flow proceed
sys.exit(0)
```

## Working with MCP Tools

Droid hooks work seamlessly with
[Model Context Protocol (MCP) tools](/cli/configuration/mcp). When MCP servers
provide tools, they appear with a special naming pattern that you can match in
your hooks.

### MCP Tool Naming

MCP tools follow the pattern `mcp__<server>__<tool>`, for example:

* `mcp__memory__create_entities` - Memory server's create entities tool
* `mcp__filesystem__read_file` - Filesystem server's read file tool
* `mcp__github__search_repositories` - GitHub server's search tool

### Configuring Hooks for MCP Tools

You can target specific MCP tools or entire MCP servers:

```json  theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory__.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Memory operation initiated' >> ~/mcp-operations.log"
          }
        ]
      },
      {
        "matcher": "mcp__.*__write.*",
        "hooks": [
          {
            "type": "command",
            "command": "/home/user/scripts/validate-mcp-write.py"
          }
        ]
      }
    ]
  }
}
```

## Examples

<Tip>
  For practical examples including code formatting, notifications, and file protection, see [More Examples](/cli/configuration/hooks-guide#more-examples) in the get started guide.
</Tip>

## Security Considerations

### Disclaimer

**USE AT YOUR OWN RISK**: Droid hooks execute arbitrary shell commands on
your system automatically. By using hooks, you acknowledge that:

* You are solely responsible for the commands you configure
* Hooks can modify, delete, or access any files your user account can access
* Malicious or poorly written hooks can cause data loss or system damage
* Factory AI provides no warranty and assumes no liability for any damages
  resulting from hook usage
* You should thoroughly test hooks in a safe environment before production use

Always review and understand any hook commands before adding them to your
configuration.

### Security Best Practices

Here are some key practices for writing more secure hooks:

1. **Validate and sanitize inputs** - Never trust input data blindly
2. **Always quote shell variables** - Use `"$VAR"` not `$VAR`
3. **Block path traversal** - Check for `..` in file paths
4. **Use absolute paths** - Always specify full paths for scripts. Never use relative paths like `./script.sh` or `hooks/script.sh` as they may resolve incorrectly depending on Droid's current directory. Use `"$FACTORY_PROJECT_DIR"/path/to/script.sh` for project scripts or full paths like `/usr/local/bin/script.sh` or `~/.factory/hooks/script.sh` for global scripts.
5. **Skip sensitive files** - Avoid `.env`, `.git/`, keys, etc.

### Configuration Safety

Direct edits to hooks in settings files don't take effect immediately. Droid:

1. Captures a snapshot of hooks at startup
2. Uses this snapshot throughout the session
3. Warns if hooks are modified externally
4. Requires review in `/hooks` menu for changes to apply

This prevents malicious hook modifications from affecting your current session.

## Hook Execution Details

* **Timeout**: 60-second execution limit by default, configurable per command.
  * A timeout for an individual command does not affect the other commands.
* **Parallelization**: All matching hooks run in parallel
* **Deduplication**: Multiple identical hook commands are deduplicated automatically
* **Environment**: Runs in current directory with Droid's environment
  * The `FACTORY_PROJECT_DIR` environment variable is available and contains the
    absolute path to the project root directory (where Droid was started)
* **Input**: JSON via stdin
* **Output**:
  * PreToolUse/PostToolUse/Stop/SubagentStop: Progress shown in transcript (Ctrl-R)
  * Notification/SessionEnd: Logged to debug only (`--debug`)
  * UserPromptSubmit/SessionStart: stdout added as context for Droid

## Debugging

### Basic Troubleshooting

If your hooks aren't working:

1. **Check configuration** - Run `/hooks` to see if your hook is registered
2. **Verify syntax** - Ensure your JSON settings are valid
3. **Test commands** - Run hook commands manually first
4. **Check permissions** - Make sure scripts are executable
5. **Review logs** - Use `droid --debug` to see hook execution details

Common issues:

* **Quotes not escaped** - Use `\"` inside JSON strings
* **Wrong matcher** - Check tool names match exactly (case-sensitive)
* **Command not found** - Use full paths for scripts

### Advanced Debugging

For complex hook issues:

1. **Inspect hook execution** - Use `droid --debug` to see detailed hook
   execution
2. **Validate JSON schemas** - Test hook input/output with external tools
3. **Check environment variables** - Verify Droid's environment is correct
4. **Test edge cases** - Try hooks with unusual file paths or inputs
5. **Monitor system resources** - Check for resource exhaustion during hook
   execution
6. **Use structured logging** - Implement logging in your hook scripts

### Debug Output Example

Use `droid --debug` to see hook execution details:

```
[DEBUG] Executing hooks for PostToolUse:Write
[DEBUG] Getting matching hook commands for PostToolUse with query: Write
[DEBUG] Found 1 hook matchers in settings
[DEBUG] Matched 1 hooks for query "Write"
[DEBUG] Found 1 hook commands to execute
[DEBUG] Executing hook command: <Your command> with timeout 60000ms
[DEBUG] Hook command completed with status 0: <Your stdout>
```

Progress messages appear in transcript mode (Ctrl-R) showing:

* Which hook is running
* Command being executed
* Success/failure status
* Output or error messages


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt
