Learn how to customize and extend Droid’s behavior by registering shell commands

Droid hooks are user-defined shell commands that execute at various points in Droid’s lifecycle. Hooks provide deterministic control over Droid’s behavior, ensuring certain actions always happen rather than relying on Droid to choose to run them.
For reference documentation on hooks, see Hooks reference. Explore the hook cookbooks.
Example use cases for hooks include:
Notifications: Customize how you get notified when Droid is awaiting your input or permission to run something.
Automatic formatting: Run prettier on .ts files, gofmt on .go files, etc. after every file edit.
Logging: Track and count all executed commands for compliance or debugging.
Feedback: Provide automated feedback when Droid produces code that does not follow your codebase conventions.
Custom permissions: Block modifications to production files or sensitive directories.
By encoding these rules as hooks rather than prompting instructions, you turn suggestions into app-level code that executes every time it is expected to run.
You must consider the security implication of hooks as you add them, because hooks run automatically during Droid’s execution with your current environment’s credentials. For example, malicious hooks code can exfiltrate your data. Always review your hooks implementation before registering them.
For full security best practices, see Security Considerations in the hooks reference documentation.
Important: Always use absolute paths when referencing scripts in your hook commands, not relative paths. Hooks execute from Droid’s current working directory, which may not be your project root. Use $FACTORY_PROJECT_DIR for project-relative scripts (e.g., "$FACTORY_PROJECT_DIR"/.factory/hooks/script.sh) or full paths for global scripts (e.g., /usr/local/bin/my-hook.sh or ~/.factory/hooks/script.sh).
​
Hook Events Overview
Droid provides several hook events that run at different points in the workflow:
PreToolUse: Runs before tool calls (can block them)
PostToolUse: Runs after tool calls complete
UserPromptSubmit: Runs when the user submits a prompt, before Droid processes it
Notification: Runs when Droid sends notifications
Stop: Runs when Droid finishes responding
SubagentStop: Runs when sub-droid tasks complete
PreCompact: Runs before Droid is about to run a compact operation
SessionStart: Runs when Droid starts a new session or resumes an existing session
SessionEnd: Runs when Droid session ends
Each event receives different data and can control Droid’s behavior in different ways.
​
Quickstart
In this quickstart, you’ll add a hook that logs the shell commands that Droid runs.
​
Prerequisites
Install jq for JSON processing in the command line.
​
Step 1: Open hooks configuration
Run the /hooks slash command and select the PreToolUse hook event.
PreToolUse hooks run before tool calls and can block them while providing Droid feedback on what to do differently.
​
Step 2: Add a matcher
Select + Add new matcher… to run your hook only on Bash tool calls.
Type Bash for the matcher.
You can use * to match all tools.
​
Step 3: Add the hook
Select + Add new hook… and enter this command:
jq -r '.tool_input.command' >> ~/.factory/bash-command-log.txt
​
Step 4: Save your configuration
For storage location, select User settings since you’re logging to your home directory. This hook will then apply to all projects, not just your current project.
Then press Esc until you return to the REPL. Your hook is now registered!
​
Step 5: Verify your hook
Run /hooks again or check ~/.factory/settings.json to see your configuration:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.command' >> ~/.factory/bash-command-log.txt"
          }
        ]
      }
    ]
  }
}
​
Step 6: Test your hook
Ask Droid to run a simple command like ls and check your log file:
cat ~/.factory/bash-command-log.txt
You should see entries like:
ls
​
More Examples
For a complete example implementation, see the bash command validator example in our public codebase.
​
Code Formatting Hook
Automatically format TypeScript files after editing:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | { read file_path; if echo \"$file_path\" | grep -q '\\.ts'; then npx prettier --write \"$file_path\"; fi; }"
          }
        ]
      }
    ]
  }
}
​
Markdown Formatting Hook
Automatically fix missing language tags and formatting issues in markdown files:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$FACTORY_PROJECT_DIR\"/.factory/hooks/markdown_formatter.py"
          }
        ]
      }
    ]
  }
}
Create .factory/hooks/markdown_formatter.py with this content:
#!/usr/bin/env python3
"""
Markdown formatter for Droid output.
Fixes missing language tags and spacing issues while preserving code content.
"""
import json
import sys
import re
import os

def detect_language(code):
    """Best-effort language detection from code content."""
    s = code.strip()

    # JSON detection
    if re.search(r'^\s*[{\[]', s):
        try:
            json.loads(s)
            return 'json'
        except:
            pass

    # Python detection
    if re.search(r'^\s*def\s+\w+\s*\(', s, re.M) or \
       re.search(r'^\s*(import|from)\s+\w+', s, re.M):
        return 'python'

    # JavaScript detection
    if re.search(r'\b(function\s+\w+\s*\(|const\s+\w+\s*=)', s) or \
       re.search(r'=>|console\.(log|error)', s):
        return 'javascript'

    # Bash detection
    if re.search(r'^#!.*\b(bash|sh)\b', s, re.M) or \
       re.search(r'\b(if|then|fi|for|in|do|done)\b', s):
        return 'bash'

    # SQL detection
    if re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|CREATE)\s+', s, re.I):
        return 'sql'

    return 'text'

def format_markdown(content):
    """Format markdown content with language detection."""
    # Fix unlabeled code fences
    def add_lang_to_fence(match):
        indent, info, body, closing = match.groups()
        if not info.strip():
            lang = detect_language(body)
            return f"{indent}```{lang}\n{body}{closing}\n"
        return match.group(0)

    fence_pattern = r'(?ms)^([ \t]{0,3})```([^\n]*)\n(.*?)(\n\1```)\s*$'
    content = re.sub(fence_pattern, add_lang_to_fence, content)

    # Fix excessive blank lines (only outside code fences)
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.rstrip() + '\n'

# Main execution
try:
    input_data = json.load(sys.stdin)
    file_path = input_data.get('tool_input', {}).get('file_path', '')

    if not file_path.endswith(('.md', '.mdx')):
        sys.exit(0)  # Not a markdown file

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        formatted = format_markdown(content)

        if formatted != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted)
            print(f"✓ Fixed markdown formatting in {file_path}")

except Exception as e:
    print(f"Error formatting markdown: {e}", file=sys.stderr)
    sys.exit(1)
Make the script executable:
chmod +x .factory/hooks/markdown_formatter.py
This hook automatically:
Detects programming languages in unlabeled code blocks
Adds appropriate language tags for syntax highlighting
Fixes excessive blank lines while preserving code content
Only processes markdown files (.md, .mdx)
​
Custom Notification Hook
Get desktop notifications when Droid needs input:
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "notify-send 'Droid' 'Awaiting your input'"
          }
        ]
      }
    ]
  }
}
​
File Protection Hook
Block edits to sensitive files:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -c \"import json, sys; data=json.load(sys.stdin); path=data.get('tool_input',{}).get('file_path',''); sys.exit(2 if any(p in path for p in ['.env', 'package-lock.json', '.git/']) else 0)\""
          }
        ]
      }
    ]
  }
}


Reference
Hooks reference

Copy page

Reference documentation for implementing hooks in Droid

For a quickstart guide with examples, see Get started with hooks.
​
Configuration
Droid hooks are configured in your settings files:
~/.factory/settings.json - User settings
.factory/settings.json - Project settings
.factory/settings.local.json - Local project settings (not committed)
Enterprise managed policy settings
​
Structure
Hooks are organized by matchers, where each matcher can have multiple hooks:
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
matcher: Pattern to match tool names, case-sensitive (only applicable for PreToolUse and PostToolUse)
Simple strings match exactly: Write matches only the Write tool
Supports regex: Edit|Write or Notebook.*
Use * to match all tools. You can also use empty string ("") or leave matcher blank.
hooks: Array of commands to execute when the pattern matches
type: Currently only "command" is supported
command: The bash command to execute (can use $FACTORY_PROJECT_DIR environment variable)
timeout: (Optional) How long a command should run, in seconds, before canceling that specific command.
Always use absolute paths for hook commands and scripts, not relative paths. Hooks execute from Droid’s current working directory, which may change during execution. Use "$FACTORY_PROJECT_DIR"/path/to/script.sh for project-relative scripts or full paths like /usr/local/bin/script.sh or ~/.factory/hooks/script.sh for global scripts.
For events like UserPromptSubmit, Notification, Stop, and SubagentStop that don’t use matchers, you can omit the matcher field:
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
​
Project-Specific Hook Scripts
You can use the environment variable FACTORY_PROJECT_DIR (only available when Droid spawns the hook command) to reference scripts stored in your project, ensuring they work regardless of Droid’s current directory:
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
​
Plugin hooks
Plugins can provide hooks that integrate seamlessly with your user and project hooks. Plugin hooks are automatically merged with your configuration when plugins are enabled.
How plugin hooks work:
Plugin hooks are defined in the plugin’s hooks/hooks.json file or in a file given by a custom path to the hooks field.
When a plugin is enabled, its hooks are merged with user and project hooks
Multiple hooks from different sources can respond to the same event
Plugin hooks use the ${DROID_PLUGIN_ROOT} environment variable to reference plugin files
Example plugin hook configuration:
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
Plugin hooks use the same format as regular hooks with an optional description field to explain the hook’s purpose.
Plugin hooks run alongside your custom hooks. If multiple hooks match an event, they all execute in parallel.
Environment variables for plugins:
${DROID_PLUGIN_ROOT}: Absolute path to the plugin directory
${FACTORY_PROJECT_DIR}: Project root directory (same as for project hooks)
All standard environment variables are available
See the plugin components reference for details on creating plugin hooks.
​
Hook Events
​
PreToolUse
Runs after Droid creates tool parameters and before processing the tool call.
Common matchers:
Task - Sub-droid tasks (see subagents documentation)
Bash - Shell commands
Glob - File pattern matching
Grep - Content search
Read - File reading
Edit - File editing
Write - File writing
WebFetch, WebSearch - Web operations
​
PostToolUse
Runs immediately after a tool completes successfully.
Recognizes the same matcher values as PreToolUse.
​
Notification
Runs when Droid sends notifications. Notifications are sent when:
Droid needs your permission to use a tool. Example: “Droid needs your permission to use Bash”
The prompt input has been idle for at least 60 seconds. “Droid is waiting for your input”
​
UserPromptSubmit
Runs when the user submits a prompt, before Droid processes it. This allows you to add additional context based on the prompt/conversation, validate prompts, or block certain types of prompts.
​
Stop
Runs when Droid has finished responding. Does not run if the stoppage occurred due to a user interrupt.
​
SubagentStop
Runs when a sub-droid (Task tool call) has finished responding.
​
PreCompact
Runs before Droid is about to run a compact operation.
Matchers:
manual - Invoked from /compact
auto - Invoked from auto-compact (due to full context window)
​
SessionStart
Runs when Droid starts a new session or resumes an existing session (which currently does start a new session under the hood). Useful for loading in development context like existing issues or recent changes to your codebase, installing dependencies, or setting up environment variables.
Matchers:
startup - Invoked from startup
resume - Invoked from --resume, --continue, or /resume
clear - Invoked from /clear
compact - Invoked from auto or manual compact.
​
SessionEnd
Runs when a Droid session ends. Useful for cleanup tasks, logging session statistics, or saving session state.
The reason field in the hook input will be one of:
clear - Session cleared with /clear command
logout - User logged out
prompt_input_exit - User exited while prompt input was visible
other - Other exit reasons
​
Hook Input
Hooks receive JSON data via stdin containing session information and event-specific data:
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
​
PreToolUse Input
The exact schema for tool_input depends on the tool.
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
​
PostToolUse Input
The exact schema for tool_input and tool_response depends on the tool.
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
​
Notification Input
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Notification",
  "message": "Task completed successfully"
}
​
UserPromptSubmit Input
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Write a function to calculate the factorial of a number"
}
​
Stop and SubagentStop Input
stop_hook_active is true when Droid is already continuing as a result of a stop hook. Check this value or process the transcript to prevent Droid from running indefinitely.
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Stop",
  "stop_hook_active": true
}
​
PreCompact Input
For manual, custom_instructions comes from what the user passes into /compact. For auto, custom_instructions is empty.
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PreCompact",
  "trigger": "manual",
  "custom_instructions": ""
}
​
SessionStart Input
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "SessionStart",
  "source": "startup"
}
​
SessionEnd Input
{
  "session_id": "abc123",
  "transcript_path": "~/.factory/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "SessionEnd",
  "reason": "exit"
}
​
Hook Output
There are two ways for hooks to return output back to Droid. The output communicates whether to block and any feedback that should be shown to Droid and the user.
​
Simple: Exit Code
Hooks communicate status through exit codes, stdout, and stderr:
Exit code 0: Success. stdout is shown to the user in transcript mode (CTRL-R), except for UserPromptSubmit and SessionStart, where stdout is added to the context.
Exit code 2: Blocking error. stderr is fed back to Droid to process automatically. See per-hook-event behavior below.
Other exit codes: Non-blocking error. stderr is shown to the user and execution continues.
Reminder: Droid does not see stdout if the exit code is 0, except for the UserPromptSubmit hook where stdout is injected as context.
​
Exit Code 2 Behavior
Hook Event	Behavior
PreToolUse	Blocks the tool call, shows stderr to Droid
PostToolUse	Shows stderr to Droid (tool already ran)
Notification	N/A, shows stderr to user only
UserPromptSubmit	Blocks prompt processing, erases prompt, shows stderr to user only
Stop	Blocks stoppage, shows stderr to Droid
SubagentStop	Blocks stoppage, shows stderr to sub-droid
PreCompact	N/A, shows stderr to user only
SessionStart	N/A, shows stderr to user only
SessionEnd	N/A, shows stderr to user only
​
Advanced: JSON Output
Hooks can return structured JSON in stdout for more sophisticated control:
​
Common JSON Fields
All hook types can include these optional fields:
{
  "continue": true, // Whether Droid should continue after hook execution (default: true)
  "stopReason": "string", // Message shown when continue is false

  "suppressOutput": true, // Hide stdout from transcript mode (default: false)
  "systemMessage": "string" // Optional warning message shown to the user
}
If continue is false, Droid stops processing after the hooks run.
For PreToolUse, this is different from "permissionDecision": "deny", which only blocks a specific tool call and provides automatic feedback to Droid.
For PostToolUse, this is different from "decision": "block", which provides automated feedback to Droid.
For UserPromptSubmit, this prevents the prompt from being processed.
For Stop and SubagentStop, this takes precedence over any "decision": "block" output.
In all cases, "continue" = false takes precedence over any "decision": "block" output.
stopReason accompanies continue with a reason shown to the user, not shown to Droid.
​
PreToolUse Decision Control
PreToolUse hooks can control whether a tool call proceeds.
"allow" bypasses the permission system. permissionDecisionReason is shown to the user but not to Droid.
"deny" prevents the tool call from executing. permissionDecisionReason is shown to Droid.
"ask" asks the user to confirm the tool call in the UI. permissionDecisionReason is shown to the user but not to Droid.
Additionally, hooks can modify tool inputs before execution using updatedInput:
updatedInput allows you to modify the tool’s input parameters before the tool executes. This is a Record<string, unknown> object containing the fields you want to change or add.
This is most useful with "permissionDecision": "allow" to modify and approve tool calls.
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
The decision and reason fields are deprecated for PreToolUse hooks. Use hookSpecificOutput.permissionDecision and hookSpecificOutput.permissionDecisionReason instead. The deprecated fields "approve" and "block" map to "allow" and "deny" respectively.
​
PostToolUse Decision Control
PostToolUse hooks can provide feedback to Droid after tool execution.
"block" automatically prompts Droid with reason.
undefined does nothing. reason is ignored.
"hookSpecificOutput.additionalContext" adds context for Droid to consider.
{
  "decision": "block" | undefined,
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Additional information for Droid"
  }
}
​
UserPromptSubmit Decision Control
UserPromptSubmit hooks can control whether a user prompt is processed.
"block" prevents the prompt from being processed. The submitted prompt is erased from context. "reason" is shown to the user but not added to context.
undefined allows the prompt to proceed normally. "reason" is ignored.
"hookSpecificOutput.additionalContext" adds the string to the context if not blocked.
{
  "decision": "block" | undefined,
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "My additional context here"
  }
}
​
Stop/SubagentStop Decision Control
Stop and SubagentStop hooks can control whether Droid must continue.
"block" prevents Droid from stopping. You must populate reason for Droid to know how to proceed.
undefined allows Droid to stop. reason is ignored.
{
  "decision": "block" | undefined,
  "reason": "Must be provided when Droid is blocked from stopping"
}
​
SessionStart Decision Control
SessionStart hooks allow you to load in context at the start of a session.
"hookSpecificOutput.additionalContext" adds the string to the context.
Multiple hooks’ additionalContext values are concatenated.
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "My additional context here"
  }
}
​
SessionEnd Decision Control
SessionEnd hooks run when a session ends. They cannot block session termination but can perform cleanup tasks.
​
Exit Code Example: Bash Command Validation
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
​
JSON Output Example: UserPromptSubmit to Add Context and Validation
For UserPromptSubmit hooks, you can inject context using either method:
Exit code 0 with stdout: Droid sees the context (special case for UserPromptSubmit)
JSON output: Provides more control over the behavior
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
​
JSON Output Example: PreToolUse with Approval
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
​
Working with MCP Tools
Droid hooks work seamlessly with Model Context Protocol (MCP) tools. When MCP servers provide tools, they appear with a special naming pattern that you can match in your hooks.
​
MCP Tool Naming
MCP tools follow the pattern mcp__<server>__<tool>, for example:
mcp__memory__create_entities - Memory server’s create entities tool
mcp__filesystem__read_file - Filesystem server’s read file tool
mcp__github__search_repositories - GitHub server’s search tool
​
Configuring Hooks for MCP Tools
You can target specific MCP tools or entire MCP servers:
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
​
Examples
For practical examples including code formatting, notifications, and file protection, see More Examples in the get started guide.
​
Security Considerations
​
Disclaimer
USE AT YOUR OWN RISK: Droid hooks execute arbitrary shell commands on your system automatically. By using hooks, you acknowledge that:
You are solely responsible for the commands you configure
Hooks can modify, delete, or access any files your user account can access
Malicious or poorly written hooks can cause data loss or system damage
Factory AI provides no warranty and assumes no liability for any damages resulting from hook usage
You should thoroughly test hooks in a safe environment before production use
Always review and understand any hook commands before adding them to your configuration.
​
Security Best Practices
Here are some key practices for writing more secure hooks:
Validate and sanitize inputs - Never trust input data blindly
Always quote shell variables - Use "$VAR" not $VAR
Block path traversal - Check for .. in file paths
Use absolute paths - Always specify full paths for scripts. Never use relative paths like ./script.sh or hooks/script.sh as they may resolve incorrectly depending on Droid’s current directory. Use "$FACTORY_PROJECT_DIR"/path/to/script.sh for project scripts or full paths like /usr/local/bin/script.sh or ~/.factory/hooks/script.sh for global scripts.
Skip sensitive files - Avoid .env, .git/, keys, etc.
​
Configuration Safety
Direct edits to hooks in settings files don’t take effect immediately. Droid:
Captures a snapshot of hooks at startup
Uses this snapshot throughout the session
Warns if hooks are modified externally
Requires review in /hooks menu for changes to apply
This prevents malicious hook modifications from affecting your current session.
​
Hook Execution Details
Timeout: 60-second execution limit by default, configurable per command.
A timeout for an individual command does not affect the other commands.
Parallelization: All matching hooks run in parallel
Deduplication: Multiple identical hook commands are deduplicated automatically
Environment: Runs in current directory with Droid’s environment
The FACTORY_PROJECT_DIR environment variable is available and contains the absolute path to the project root directory (where Droid was started)
Input: JSON via stdin
Output:
PreToolUse/PostToolUse/Stop/SubagentStop: Progress shown in transcript (Ctrl-R)
Notification/SessionEnd: Logged to debug only (--debug)
UserPromptSubmit/SessionStart: stdout added as context for Droid
​
Debugging
​
Basic Troubleshooting
If your hooks aren’t working:
Check configuration - Run /hooks to see if your hook is registered
Verify syntax - Ensure your JSON settings are valid
Test commands - Run hook commands manually first
Check permissions - Make sure scripts are executable
Review logs - Use droid --debug to see hook execution details
Common issues:
Quotes not escaped - Use \" inside JSON strings
Wrong matcher - Check tool names match exactly (case-sensitive)
Command not found - Use full paths for scripts
​
Advanced Debugging
For complex hook issues:
Inspect hook execution - Use droid --debug to see detailed hook execution
Validate JSON schemas - Test hook input/output with external tools
Check environment variables - Verify Droid’s environment is correct
Test edge cases - Try hooks with unusual file paths or inputs
Monitor system resources - Check for resource exhaustion during hook execution
Use structured logging - Implement logging in your hook scripts
​
Debug Output Example
Use droid --debug to see hook execution details:
[DEBUG] Executing hooks for PostToolUse:Write
[DEBUG] Getting matching hook commands for PostToolUse with query: Write
[DEBUG] Found 1 hook matchers in settings
[DEBUG] Matched 1 hooks for query "Write"
[DEBUG] Found 1 hook commands to execute
[DEBUG] Executing hook command: <Your command> with timeout 60000ms
[DEBUG] Hook command completed with status 0: <Your stdout>
Progress messages appear in transcript mode (Ctrl-R) showing:
Which hook is running
Command being executed
Success/failure status
Output or error messages


Auto-formatting Code

Copy page

Automatically format code after every file edit using hooks

This cookbook shows how to automatically format code after Droid edits files, ensuring consistent code style across your project without manual intervention.
​
How it works
The hook:
Triggers on file edits: Runs after Write or Edit tool calls
Detects file type: Checks file extension to determine formatter
Runs appropriate formatter: Executes prettier, black, gofmt, rustfmt, etc.
Provides feedback: Reports formatting results to the user
Handles errors gracefully: Continues even if formatting fails
​
Prerequisites
Install formatters for your language stack:

JavaScript/TypeScript

Python

Go

Rust
npm install -D prettier
​
Basic setup
​
Single language project
For a JavaScript/TypeScript project, add this to your .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | { read file_path; if echo \"$file_path\" | grep -qE '\\.(ts|tsx|js|jsx)$'; then npx prettier --write \"$file_path\" 2>&1 && echo \"✓ Formatted $file_path\"; fi; }",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Multi-language project
For projects with multiple languages, use a script to handle different file types.
Create .factory/hooks/format.sh:
#!/bin/bash
set -e

# Read the hook input
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

# Skip if file doesn't exist
if [ ! -f "$file_path" ]; then
  exit 0
fi

# Determine formatter based on file extension
case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.json|*.css|*.scss|*.md|*.mdx)
    if command -v prettier &> /dev/null; then
      prettier --write "$file_path" 2>&1
      echo "✓ Formatted with Prettier: $file_path"
    fi
    ;;
  *.py)
    if command -v black &> /dev/null; then
      black "$file_path" 2>&1
      echo "✓ Formatted with Black: $file_path"
    fi
    if command -v isort &> /dev/null; then
      isort "$file_path" 2>&1
      echo "✓ Sorted imports with isort: $file_path"
    fi
    ;;
  *.go)
    if command -v gofmt &> /dev/null; then
      gofmt -w "$file_path" 2>&1
      echo "✓ Formatted with gofmt: $file_path"
    fi
    ;;
  *.rs)
    if command -v rustfmt &> /dev/null; then
      rustfmt "$file_path" 2>&1
      echo "✓ Formatted with rustfmt: $file_path"
    fi
    ;;
  *.java)
    if command -v google-java-format &> /dev/null; then
      google-java-format -i "$file_path" 2>&1
      echo "✓ Formatted with google-java-format: $file_path"
    fi
    ;;
  *)
    # No formatter for this file type
    exit 0
    ;;
esac

exit 0
Make the script executable:
chmod +x .factory/hooks/format.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/format.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Advanced configurations
​
Format with custom config
Use project-specific prettier config:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | { read file_path; if echo \"$file_path\" | grep -qE '\\.(ts|tsx|js|jsx)$'; then npx prettier --config \"$DROID_PROJECT_DIR\"/.prettierrc --write \"$file_path\" 2>&1; fi; }",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Format with linting
Combine formatting with linting fixes.
Create .factory/hooks/format-and-lint.sh:
#!/bin/bash
set -e

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

if [ ! -f "$file_path" ]; then
  exit 0
fi

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    # Format with prettier
    if command -v prettier &> /dev/null; then
      prettier --write "$file_path" 2>&1
      echo "✓ Formatted: $file_path"
    fi

    # Fix lint issues
    if command -v eslint &> /dev/null; then
      eslint --fix "$file_path" 2>&1 || true
      echo "✓ Linted: $file_path"
    fi
    ;;
  *.py)
    # Format with black
    if command -v black &> /dev/null; then
      black "$file_path" 2>&1
      echo "✓ Formatted with Black: $file_path"
    fi

    # Sort imports
    if command -v isort &> /dev/null; then
      isort "$file_path" 2>&1
      echo "✓ Sorted imports: $file_path"
    fi

    # Run flake8 for style issues
    if command -v flake8 &> /dev/null; then
      flake8 "$file_path" 2>&1 || true
      echo "✓ Checked with flake8: $file_path"
    fi
    ;;
esac

exit 0
Make the script executable:
chmod +x .factory/hooks/format-and-lint.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/format-and-lint.sh",
            "timeout": 45
          }
        ]
      }
    ]
  }
}
​
Conditional formatting
Only format files in specific directories.
Create .factory/hooks/format-src-only.sh:
#!/bin/bash
set -e

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

# Only format files in src/ or packages/ directories
if ! echo "$file_path" | grep -qE '^(src/|packages/)'; then
  exit 0
fi

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    if command -v prettier &> /dev/null; then
      prettier --write "$file_path" 2>&1
      echo "✓ Formatted: $file_path"
    fi
    ;;
esac

exit 0
Make the script executable:
chmod +x .factory/hooks/format-src-only.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/format-src-only.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Real-world examples
​
Example 1: React component formatting
Before Hook
After Hook
// Droid creates this file
import React from 'react';
import {useState} from 'react';

export const Button = ({onClick,label}:{onClick:()=>void;label:string})=>{
const [loading,setLoading]=useState(false);
return <button onClick={onClick} disabled={loading}>{label}</button>
}
​
Example 2: Python import sorting
Before Hook
After Hook
# Droid creates this file
from typing import Optional
import sys
from django.db import models
import os
from myapp.utils import helper

def process_data(data: Optional[str]) -> None:
    if data:
        helper(data)
​
Best practices
Formatters can sometimes introduce subtle bugs (e.g., changing string formats, line continuations). Always review changes before committing.
1
Start with read-only mode

Test your formatter configuration manually first:
# Dry run to see what would change
prettier --check src/
black --check src/
2
Use consistent config files

Ensure formatter configs are committed:
# Add to version control
git add .prettierrc .prettierignore
git add pyproject.toml  # for black config
3
Set appropriate timeouts

Large files may need more time:
{
  "timeout": 60  // Increase for large files
}
4
Handle formatter errors gracefully

Don’t block Droid if formatting fails:
# Use || true to continue on errors
prettier --write "$file_path" 2>&1 || true
5
Consider Git hooks integration

Combine with pre-commit hooks for consistency:
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.0.0
    hooks:
      - id: prettier
​
Troubleshooting
​
Formatter not found
Problem: command not found error
Solution: Install the formatter globally or use npx/project binaries:
# Install globally
npm install -g prettier

# Or use project version
npx prettier --write "$file_path"
​
Formatting breaks code
Problem: Formatter introduces syntax errors
Solution: Add file validation after formatting:
# For TypeScript
prettier --write "$file_path"
tsc --noEmit "$file_path" || echo "⚠️ Type errors after formatting"
​
Hook runs too slowly
Problem: Formatting takes too long
Solution: Only format changed files, use faster formatters:
# Skip files that haven't changed
if git diff --quiet "$file_path"; then
  exit 0
fi
​
Conflicts with editor formatting
Problem: Editor and hook format differently
Solution: Use the same config for both:
// .vscode/settings.json
{
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.formatOnSave": true,
  "prettier.configPath": ".prettierrc"
}
​


Hooks
Code Validation Hooks

Copy page

Enforce code standards, security policies, and best practices automatically

This cookbook shows how to use hooks to validate code changes, enforce security policies, and maintain code quality standards before Droid makes changes.
​
How it works
Validation hooks can:
Block unsafe operations: Prevent edits to sensitive files or directories
Enforce standards: Check code against style guides and best practices
Validate security: Scan for secrets, vulnerabilities, and security issues
Provide feedback: Give Droid specific guidance on what to fix
Run checks: Execute linters, type checkers, and custom validators
​
Prerequisites
Install validation tools for your stack:

JavaScript/TypeScript

Python

Go

Security Tools
npm install -D eslint typescript @typescript-eslint/parser
npm install -D semgrep  # For security scanning
​
Basic validation
​
Block sensitive file edits
Prevent Droid from modifying critical files.
Create .factory/hooks/protect-files.sh:
#!/bin/bash

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Skip if no file path
if [ -z "$file_path" ]; then
  exit 0
fi

# List of protected patterns
protected_patterns=(
  "\.env"
  "\.env\."
  "package-lock\.json"
  "yarn\.lock"
  "\.git/"
  "node_modules/"
  "dist/"
  "build/"
  "secrets/"
  "\.pem$"
  "\.key$"
  "\.p12$"
  "credentials\.json"
)

# Check if file matches any protected pattern
for pattern in "${protected_patterns[@]}"; do
  if echo "$file_path" | grep -qE "$pattern"; then
    echo "❌ Cannot modify protected file: $file_path" >&2
    echo "This file is protected by project policy." >&2
    echo "If you need to modify it, please do so manually." >&2
    exit 2  # Exit code 2 blocks the operation
  fi
done

exit 0
chmod +x .factory/hooks/protect-files.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/protect-files.sh",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
​
Validate TypeScript syntax
Check TypeScript files for type errors before accepting edits.
Create .factory/hooks/validate-typescript.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only validate TypeScript files
if ! echo "$file_path" | grep -qE '\.(ts|tsx)$'; then
  exit 0
fi

# For Write operations, validate the content directly
if [ "$tool_name" = "Write" ]; then
  content=$(echo "$input" | jq -r '.tool_input.content')

  # Write to temp file for validation
  temp_file=$(mktemp --suffix=.ts)
  echo "$content" > "$temp_file"

  # Run TypeScript compiler on temp file
  if ! npx tsc --noEmit "$temp_file" 2>&1; then
    rm "$temp_file"
    echo "❌ TypeScript validation failed" >&2
    echo "The code contains type errors. Please fix them before proceeding." >&2
    exit 2
  fi

  rm "$temp_file"
fi

# For Edit operations, validate the file will be valid after edit
# (This requires reading the file and applying the edit, which is complex)
# For now, we'll validate post-edit in PostToolUse

exit 0
chmod +x .factory/hooks/validate-typescript.sh
For PostToolUse validation:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | { read file_path; if echo \"$file_path\" | grep -qE '\\.(ts|tsx)$' && [ -f \"$file_path\" ]; then npx tsc --noEmit \"$file_path\" 2>&1 || { echo '⚠️ Type errors detected in '$file_path >&2; }; fi; }",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Security validation
​
Secret detection
Prevent committing secrets and credentials.
Create .factory/hooks/scan-secrets.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only scan file write/edit operations
if [ "$tool_name" != "Write" ] && [ "$tool_name" != "Edit" ]; then
  exit 0
fi

# Skip non-text files
if echo "$file_path" | grep -qE '\.(jpg|png|gif|pdf|zip|tar|gz)$'; then
  exit 0
fi

# Get content to scan
if [ "$tool_name" = "Write" ]; then
  content=$(echo "$input" | jq -r '.tool_input.content')
else
  # For Edit, we'd need to check the file after edit (PostToolUse is better)
  exit 0
fi

# Create temp file for scanning
temp_file=$(mktemp)
echo "$content" > "$temp_file"

# Pattern-based secret detection
secret_patterns=(
  "AKIA[0-9A-Z]{16}"  # AWS Access Key
  "AIza[0-9A-Za-z\\-_]{35}"  # Google API Key
  "sk-[a-zA-Z0-9]{32,}"  # OpenAI API Key
  "[a-f0-9]{32}"  # Generic 32-char hex (MD5)
  "ghp_[a-zA-Z0-9]{36}"  # GitHub Personal Access Token
  "glpat-[a-zA-Z0-9\\-]{20}"  # GitLab Personal Access Token
)

found_secrets=0

for pattern in "${secret_patterns[@]}"; do
  if grep -qE "$pattern" "$temp_file"; then
    echo "❌ Potential secret detected matching pattern: $pattern" >&2
    found_secrets=1
  fi
done

# Also check for common variable names with suspicious values
if grep -qE "(password|secret|key|token|api_key)\s*[:=]\s*['\"][^'\"]{8,}" "$temp_file"; then
  echo "⚠️ Suspicious credential-like assignment detected" >&2
  echo "Review: $(grep -E "(password|secret|key|token|api_key)\s*[:=]" "$temp_file" | head -1)" >&2
  found_secrets=1
fi

rm "$temp_file"

if [ $found_secrets -eq 1 ]; then
  echo "" >&2
  echo "Please use environment variables or secure secret management instead." >&2
  exit 2  # Block the operation
fi

exit 0
chmod +x .factory/hooks/scan-secrets.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/scan-secrets.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
​
Dependency security scanning
Check for vulnerable dependencies.
Create .factory/hooks/check-deps.sh:
#!/bin/bash

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only check package files
if [[ ! "$file_path" =~ (package\.json|requirements\.txt|go\.mod|Cargo\.toml)$ ]]; then
  exit 0
fi

echo "🔍 Checking for vulnerable dependencies..."

case "$file_path" in
  *package.json)
    if command -v npm &> /dev/null; then
      # Run npm audit
      if ! npm audit --audit-level=high 2>&1; then
        echo "⚠️ Vulnerable dependencies detected" >&2
        echo "Run 'npm audit fix' to resolve issues" >&2
        # Don't block, just warn
        exit 0
      fi
    fi
    ;;

  *requirements.txt)
    if command -v pip-audit &> /dev/null; then
      if ! pip-audit -r "$file_path" 2>&1; then
        echo "⚠️ Vulnerable Python packages detected" >&2
        exit 0
      fi
    fi
    ;;

  *Cargo.toml)
    if command -v cargo-audit &> /dev/null; then
      if ! cargo audit 2>&1; then
        echo "⚠️ Vulnerable Rust crates detected" >&2
        exit 0
      fi
    fi
    ;;
esac

exit 0
chmod +x .factory/hooks/check-deps.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/check-deps.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Code quality validation
​
Enforce linting rules
Validate code against linting rules before accepting changes.
Create .factory/hooks/lint-check.sh:
#!/bin/bash

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

if [ ! -f "$file_path" ]; then
  # File doesn't exist yet (Write operation), skip for now
  exit 0
fi

# Run appropriate linter based on file type
case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    if command -v eslint &> /dev/null; then
      if ! eslint "$file_path" 2>&1; then
        echo "" >&2
        echo "❌ ESLint found issues in $file_path" >&2
        echo "Please fix the linting errors above." >&2
        exit 2  # Block the operation
      fi
      echo "✓ ESLint passed for $file_path"
    fi
    ;;

  *.py)
    if command -v flake8 &> /dev/null; then
      if ! flake8 "$file_path" 2>&1; then
        echo "" >&2
        echo "❌ Flake8 found issues in $file_path" >&2
        exit 2
      fi
      echo "✓ Flake8 passed for $file_path"
    fi
    ;;

  *.go)
    if command -v golint &> /dev/null; then
      if ! golint "$file_path" 2>&1; then
        echo "" >&2
        echo "❌ Golint found issues in $file_path" >&2
        exit 2
      fi
    fi
    ;;

  *.rs)
    if command -v clippy &> /dev/null; then
      if ! cargo clippy -- -D warnings 2>&1; then
        echo "❌ Clippy found issues" >&2
        exit 2
      fi
    fi
    ;;
esac

exit 0
chmod +x .factory/hooks/lint-check.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/lint-check.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Complexity checks
Reject overly complex code.
Create .factory/hooks/check-complexity.py:
#!/usr/bin/env python3
"""
Check code complexity and reject changes that are too complex.
Uses radon for Python, or custom heuristics for other languages.
"""
import json
import sys
import subprocess
import re

def check_python_complexity(file_path):
    """Check Python file complexity using radon."""
    try:
        result = subprocess.run(
            ['radon', 'cc', file_path, '-s', '-n', 'C'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout:
            print(f"❌ Code complexity too high in {file_path}", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print("\nPlease simplify the code by:", file=sys.stderr)
            print("- Breaking down large functions", file=sys.stderr)
            print("- Reducing nesting levels", file=sys.stderr)
            print("- Extracting helper functions", file=sys.stderr)
            return False

    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return True

def check_js_complexity(file_path):
    """Basic complexity check for JavaScript/TypeScript."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Count nesting level (very basic check)
    max_nesting = 0
    current_nesting = 0

    for char in content:
        if char == '{':
            current_nesting += 1
            max_nesting = max(max_nesting, current_nesting)
        elif char == '}':
            current_nesting -= 1

    if max_nesting > 5:
        print(f"⚠️ High nesting level ({max_nesting}) in {file_path}", file=sys.stderr)
        print("Consider refactoring to reduce nesting.", file=sys.stderr)
        # Warning only, don't block

    return True

try:
    input_data = json.load(sys.stdin)
    file_path = input_data.get('tool_input', {}).get('file_path', '')

    if not file_path:
        sys.exit(0)

    if file_path.endswith('.py'):
        if not check_python_complexity(file_path):
            sys.exit(2)
    elif file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
        if not check_js_complexity(file_path):
            sys.exit(2)

except Exception as e:
    print(f"Error checking complexity: {e}", file=sys.stderr)
    sys.exit(0)  # Don't block on errors
chmod +x .factory/hooks/check-complexity.py
pip install radon  # For Python complexity checking
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/check-complexity.py",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
​
Advanced validation
​
Custom business logic validation
Enforce domain-specific rules.
Create .factory/hooks/validate-business-logic.sh:
#!/bin/bash

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')
content=$(echo "$input" | jq -r '.tool_input.content // ""')

# Example: Ensure API routes have authentication
if echo "$file_path" | grep -qE 'routes/.*\.ts$'; then
  if echo "$content" | grep -qE 'router\.(get|post|put|delete)' && \
     ! echo "$content" | grep -qE '(authenticate|requireAuth|isAuthenticated)'; then
    echo "❌ API routes must include authentication middleware" >&2
    echo "Add authenticate() or requireAuth() to your route handlers." >&2
    exit 2
  fi
fi

# Example: Ensure database queries use parameterized statements
if echo "$content" | grep -qE 'db\.query\([^?]*\$\{'; then
  echo "❌ SQL injection risk detected" >&2
  echo "Use parameterized queries instead of string interpolation." >&2
  echo "Bad:  db.query(\`SELECT * FROM users WHERE id = \${id}\`)" >&2
  echo "Good: db.query('SELECT * FROM users WHERE id = ?', [id])" >&2
  exit 2
fi

# Example: Ensure React components have prop type validation
if echo "$file_path" | grep -qE 'components/.*\.(tsx|jsx)$'; then
  if echo "$content" | grep -qE 'export (const|function)' && \
     ! echo "$content" | grep -qE '(PropTypes|interface.*Props|type.*Props)'; then
    echo "⚠️ React component should have prop type definitions" >&2
    echo "Consider adding TypeScript interfaces or PropTypes." >&2
    # Warning only, don't block
  fi
fi

exit 0
chmod +x .factory/hooks/validate-business-logic.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/validate-business-logic.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
​
Architecture compliance
Ensure code follows architecture patterns.
Create .factory/hooks/check-architecture.py:
#!/usr/bin/env python3
"""
Enforce architectural boundaries and patterns.
"""
import json
import sys
import os
import re

ARCHITECTURE_RULES = {
    # Frontend components shouldn't import from backend
    r'src/frontend/.*\.tsx?$': {
        'forbidden_imports': [r'src/backend/', r'../backend/'],
        'message': 'Frontend code cannot import from backend'
    },

    # Domain layer shouldn't import from infrastructure
    r'src/domain/.*\.ts$': {
        'forbidden_imports': [r'src/infrastructure/', r'express', r'axios'],
        'message': 'Domain layer must be framework-agnostic'
    },

    # Tests shouldn't import from src
    r'tests/.*\.test\.ts$': {
        'forbidden_imports': [r'src/(?!test-utils)'],
        'message': 'Tests should use public APIs, not internal imports'
    },
}

def check_imports(file_path, content):
    """Check if imports violate architecture rules."""
    for pattern, rule in ARCHITECTURE_RULES.items():
        if re.search(pattern, file_path):
            # Extract all imports from the file
            import_pattern = r'from [\'"](.+?)[\'"]|import .+ from [\'"](.+?)[\'"]'
            imports = re.findall(import_pattern, content)

            for imp in imports:
                import_path = imp[0] or imp[1]

                # Check against forbidden patterns
                for forbidden in rule['forbidden_imports']:
                    if re.search(forbidden, import_path):
                        print(f"❌ Architecture violation in {file_path}", file=sys.stderr)
                        print(f"   {rule['message']}", file=sys.stderr)
                        print(f"   Forbidden import: {import_path}", file=sys.stderr)
                        return False

    return True

try:
    input_data = json.load(sys.stdin)
    file_path = input_data.get('tool_input', {}).get('file_path', '')
    content = input_data.get('tool_input', {}).get('content', '')

    if not file_path or not content:
        sys.exit(0)

    if not check_imports(file_path, content):
        sys.exit(2)

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(0)
chmod +x .factory/hooks/check-architecture.py
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/check-architecture.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
​
Best practices
1
Provide clear feedback

When blocking operations, explain what’s wrong and how to fix it:
echo "❌ Problem: TypeScript errors found" >&2
echo "Solution: Fix the type errors shown above" >&2
echo "Example: Add proper type annotations to parameters" >&2
exit 2
2
Use warnings vs. errors appropriately

Not everything needs to block Droid:
# Warning (exit 0) - inform but don't block
echo "⚠️ Code complexity is high, consider refactoring" >&2
exit 0

# Error (exit 2) - block the operation
echo "❌ Secret detected, cannot proceed" >&2
exit 2
3
Performance matters

Keep validation fast:
# Use grep for quick checks before expensive operations
if grep -q "password" "$file"; then
  # Only run expensive scan if simple check passes
  run_detailed_security_scan "$file"
fi
4
Make rules configurable

Allow teams to customize validation:
# Read config from project settings
MAX_COMPLEXITY="${DROID_MAX_COMPLEXITY:-10}"
ENFORCE_TESTS="${DROID_ENFORCE_TESTS:-false}"
5
Test your validators

Create test files that should pass and fail:
# Create test cases
echo '{"tool_input":{"file_path":"test.ts","content":"..."}}' | \
  .factory/hooks/validate.sh
​
Troubleshooting
​
False positives
Problem: Validation blocks legitimate code
Solution: Add exclusion patterns:
# Skip test files
if echo "$file_path" | grep -qE '\.(test|spec)\.(ts|js)$'; then
  exit 0
fi

# Skip generated files
if echo "$file_path" | grep -qE '(generated|\.gen\.)'; then
  exit 0
fi
​
Validation too slow
Problem: Hooks take too long to run
Solution: Optimize validation:
# Cache validation results
CACHE_FILE="/tmp/droid-validation-$(md5sum "$file_path" | cut -d' ' -f1)"

if [ -f "$CACHE_FILE" ]; then
  # File hasn't changed, use cached result
  exit 0
fi

# Run validation...
touch "$CACHE_FILE"
​
Inconsistent with CI
Problem: Hook passes but CI fails
Solution: Use same tools and configs:
# Use exact same commands as CI
# .github/workflows/ci.yml:
#   npm run lint

# Hook should run:
npm run lint "$file_path"

Documentation Sync

Copy page

Keep documentation in sync with code changes automatically

This cookbook shows how to automatically update documentation when code changes, ensure docs stay current, and generate API documentation from code.
​
How it works
Documentation sync hooks can:
Update API docs: Generate documentation from code annotations
Sync code examples: Keep examples in docs matching actual code
Validate doc references: Ensure docs reference correct code paths
Update changelogs: Auto-generate changelog entries
Check doc completeness: Require documentation for new features
​
Prerequisites
Install documentation tools:

TypeScript/JavaScript

Python

Go
npm install -D typedoc jsdoc documentation
npm install -D @readme/openapi-parser  # For OpenAPI
​
Basic documentation automation
​
Auto-generate API docs
Generate API documentation when code changes.
Create .factory/hooks/generate-api-docs.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only process code files
if ! echo "$file_path" | grep -qE '\.(ts|tsx|js|jsx|py|go)$'; then
  exit 0
fi

# Skip test files
if echo "$file_path" | grep -qE '\.(test|spec)\.(ts|tsx|js|jsx)$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "📚 Updating API documentation..."

case "$file_path" in
  *.ts|*.tsx)
    # TypeScript - use typedoc
    if command -v typedoc &> /dev/null && [ -f "typedoc.json" ]; then
      echo "Generating TypeScript docs..."
      typedoc --out docs/api src/ 2>&1 || {
        echo "⚠️ Failed to generate docs" >&2
      }
      echo "✓ API docs updated at docs/api"
    fi
    ;;

  *.py)
    # Python - use pdoc
    if command -v pdoc &> /dev/null; then
      module_name=$(echo "$file_path" | sed 's|^src/||; s|/|.|g; s|\.py$||')
      echo "Generating Python docs for $module_name..."

      pdoc --html --output-dir docs/api "$module_name" --force 2>&1 || {
        echo "⚠️ Failed to generate docs" >&2
      }
      echo "✓ API docs updated"
    fi
    ;;

  *.go)
    # Go - use godoc
    if command -v godoc &> /dev/null; then
      echo "Generating Go docs..."
      # Go docs are typically served, not generated
      # But we can create markdown from godoc
      echo "✓ Go docs available via 'godoc -http=:6060'"
    fi
    ;;
esac

exit 0
chmod +x .factory/hooks/generate-api-docs.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/generate-api-docs.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
​
Update README on project changes
Keep README in sync with project structure.
Create .factory/hooks/update-readme.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only update on package.json or structure changes
if ! echo "$file_path" | grep -qE '(package\.json|README\.md)$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Don't run if README is the file being edited
if [ "$file_path" = "README.md" ]; then
  exit 0
fi

echo "📝 Checking README..."

# Update package info in README
if [ -f "package.json" ] && [ -f "README.md" ]; then
  name=$(jq -r '.name' package.json)
  version=$(jq -r '.version' package.json)
  description=$(jq -r '.description' package.json)

  # Check if version in README matches package.json
  if ! grep -q "Version: $version" README.md; then
    echo "⚠️ README version out of sync with package.json"
    echo "Package version: $version"
    echo "Consider updating README.md or ask me to do it"
  fi
fi

# Check for missing documentation sections
required_sections=("Installation" "Usage" "API" "Contributing")
missing_sections=()

for section in "${required_sections[@]}"; do
  if ! grep -qi "## $section" README.md; then
    missing_sections+=("$section")
  fi
done

if [ ${#missing_sections[@]} -gt 0 ]; then
  echo "⚠️ README missing sections:"
  printf '  - %s\n' "${missing_sections[@]}"
fi

exit 0
chmod +x .factory/hooks/update-readme.sh
​
Sync code examples in documentation
Ensure code examples in docs match actual code:
Create .factory/hooks/sync-doc-examples.py:
#!/usr/bin/env python3
"""
Sync code examples in markdown docs with actual source code.
"""
import json
import sys
import re
import os

def extract_code_snippets(doc_file):
    """Extract code snippets from markdown file."""
    with open(doc_file, 'r') as f:
        content = f.read()

    # Find code blocks with source file annotations
    # Format: ```typescript
    # // From: src/components/Button.tsx
    pattern = r'```(\w+)\n// From: (.*?)\n(.*?)\n```'
    snippets = re.findall(pattern, content, re.DOTALL)

    return snippets

def verify_snippet_matches_source(language, source_file, snippet):
    """Check if snippet exists in source file."""
    if not os.path.exists(source_file):
        return False, f"Source file not found: {source_file}"

    with open(source_file, 'r') as f:
        source_content = f.read()

    # Normalize whitespace for comparison
    normalized_snippet = ' '.join(snippet.split())
    normalized_source = ' '.join(source_content.split())

    if normalized_snippet in normalized_source:
        return True, "Snippet matches source"
    else:
        return False, "Snippet does not match source code"

def main():
    input_data = json.load(sys.stdin)
    file_path = input_data.get('tool_input', {}).get('file_path', '')

    # Check both code files and doc files
    if file_path.endswith(('.md', '.mdx')):
        # Doc file changed - verify all examples
        print(f"📖 Verifying code examples in {file_path}...")

        snippets = extract_code_snippets(file_path)
        issues = []

        for lang, source, snippet in snippets:
            matches, message = verify_snippet_matches_source(lang, source, snippet)
            if not matches:
                issues.append(f"{source}: {message}")

        if issues:
            print("⚠️ Some code examples may be outdated:", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            print("\nConsider updating the examples in the documentation.", file=sys.stderr)
        else:
            print("✓ All code examples are in sync")

    elif file_path.endswith(('.ts', '.tsx', '.js', '.jsx', '.py')):
        # Code file changed - check if it's referenced in docs
        print(f"Checking if {file_path} is referenced in documentation...")

        # Find docs that reference this file
        doc_files = []
        for root, dirs, files in os.walk('docs'):
            for file in files:
                if file.endswith(('.md', '.mdx')):
                    doc_path = os.path.join(root, file)
                    with open(doc_path, 'r') as f:
                        if file_path in f.read():
                            doc_files.append(doc_path)

        if doc_files:
            print(f"ℹ️ File is referenced in {len(doc_files)} documentation file(s):")
            for doc in doc_files:
                print(f"  - {doc}")
            print("\nConsider updating these docs if the API changed.")

    sys.exit(0)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(0)
chmod +x .factory/hooks/sync-doc-examples.py
​
Advanced documentation automation
​
OpenAPI/Swagger spec validation
Ensure API documentation matches implementation:
Create .factory/hooks/validate-openapi.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Check if this is an API route file
if ! echo "$file_path" | grep -qE 'routes/.*\.(ts|js)$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Check if OpenAPI spec exists
if [ ! -f "openapi.yaml" ] && [ ! -f "swagger.yaml" ]; then
  exit 0
fi

spec_file="openapi.yaml"
[ -f "swagger.yaml" ] && spec_file="swagger.yaml"

echo "🔍 Validating OpenAPI spec..."

# Extract route definitions from code
# This is simplified - you'd need a more sophisticated parser
routes=$(grep -E "router\.(get|post|put|delete|patch)" "$file_path" | \
  sed -E "s/.*router\.([a-z]+)\(['\"](.*?)['\"].*/\1 \2/" || true)

if [ -n "$routes" ]; then
  echo "Routes in $file_path:"
  echo "$routes" | sed 's/^/  /'

  # Check if routes are documented in OpenAPI spec
  while IFS= read -r route; do
    method=$(echo "$route" | awk '{print $1}')
    path=$(echo "$route" | awk '{print $2}')

    if ! grep -q "$path" "$spec_file"; then
      echo "⚠️ Route not documented in $spec_file: $method $path"
      echo "Consider adding this endpoint to the API documentation."
    fi
  done <<< "$routes"
fi

# Validate spec syntax
if command -v swagger-cli &> /dev/null; then
  if swagger-cli validate "$spec_file" 2>&1; then
    echo "✓ OpenAPI spec is valid"
  else
    echo "❌ OpenAPI spec has errors" >&2
  fi
fi

exit 0
chmod +x .factory/hooks/validate-openapi.sh
​
JSDoc/TSDoc enforcement
Require documentation comments for public APIs:
Create .factory/hooks/enforce-jsdoc.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')
content=$(echo "$input" | jq -r '.tool_input.content // ""')

# Only check TypeScript/JavaScript files
if ! echo "$file_path" | grep -qE '\.(ts|tsx|js|jsx)$'; then
  exit 0
fi

# Skip test files
if echo "$file_path" | grep -qE '\.(test|spec)\.(ts|tsx|js|jsx)$'; then
  exit 0
fi

# Check for exported functions/classes without JSDoc
missing_docs=()

# Find exported functions without JSDoc
while IFS= read -r line; do
  # Check if line is an export
  if echo "$line" | grep -qE '^export (function|class|const|interface|type)'; then
    # Get the name
    name=$(echo "$line" | sed -E 's/^export (function|class|const|interface|type) ([a-zA-Z0-9_]+).*/\2/')

    # Check if there's a JSDoc comment before it
    # This is simplified - you'd want a proper parser
    if ! echo "$content" | grep -B1 "^export.*$name" | grep -qE '^\s*\*'; then
      missing_docs+=("$name")
    fi
  fi
done <<< "$content"

if [ ${#missing_docs[@]} -gt 0 ]; then
  echo "⚠️ Exported items missing documentation:" >&2
  printf '  - %s\n' "${missing_docs[@]}" >&2
  echo "" >&2
  echo "Please add JSDoc comments for public APIs:" >&2
  echo "/**" >&2
  echo " * Description of what this does" >&2
  echo " * @param paramName - Parameter description" >&2
  echo " * @returns Return value description" >&2
  echo " */" >&2

  # Warning only, don't block
  # Change to exit 2 to enforce documentation
fi

exit 0
chmod +x .factory/hooks/enforce-jsdoc.sh
​
Generate changelog from commits
Automatically build changelog from git history:
Create .factory/hooks/generate-changelog.sh:
#!/bin/bash
set -e

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')

# Only run on Stop (after work is complete)
if [ "$hook_event" != "Stop" ]; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Check if there are new commits since last changelog update
if [ ! -f "CHANGELOG.md" ]; then
  exit 0
fi

# Get last version in changelog
last_version=$(grep -m1 "## \[" CHANGELOG.md | sed -E 's/.*\[([0-9.]+)\].*/\1/')

if [ -z "$last_version" ]; then
  exit 0
fi

# Get commits since last version tag
if git rev-parse "v$last_version" &>/dev/null; then
  new_commits=$(git log "v$last_version..HEAD" --oneline)

  if [ -n "$new_commits" ]; then
    echo "📝 New commits since v$last_version"
    echo ""
    echo "Consider updating CHANGELOG.md with:"
    echo ""

    # Group commits by type
    echo "### Features"
    git log "v$last_version..HEAD" --oneline | grep "^[a-f0-9]* feat" | sed 's/^[a-f0-9]* feat[:(]/- /' || true
    echo ""

    echo "### Bug Fixes"
    git log "v$last_version..HEAD" --oneline | grep "^[a-f0-9]* fix" | sed 's/^[a-f0-9]* fix[:(]/- /' || true
    echo ""
  fi
fi

exit 0
chmod +x .factory/hooks/generate-changelog.sh
​
Docs coverage report
Track which code has documentation:
Create .factory/hooks/docs-coverage.py:
#!/usr/bin/env python3
"""
Calculate documentation coverage for the codebase.
"""
import os
import re
import sys
import json

def count_functions(file_path):
    """Count functions in a file."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Count function definitions (simplified)
    if file_path.endswith('.py'):
        functions = re.findall(r'^def \w+\(', content, re.MULTILINE)
    elif file_path.endswith(('.ts', '.tsx', '.js', '.jsx')):
        functions = re.findall(r'(^export function \w+|^function \w+|const \w+ = \(.*\) =>)',
                              content, re.MULTILINE)
    else:
        return 0

    return len(functions)

def count_documented_functions(file_path):
    """Count functions with documentation."""
    with open(file_path, 'r') as f:
        content = f.read()

    if file_path.endswith('.py'):
        # Look for docstrings
        pattern = r'def \w+\(.*?\):\s*"""'
    elif file_path.endswith(('.ts', '.tsx', '.js', '.jsx')):
        # Look for JSDoc comments
        pattern = r'/\*\*.*?\*/\s*(export )?function \w+'
    else:
        return 0

    documented = re.findall(pattern, content, re.DOTALL)
    return len(documented)

def main():
    # Calculate documentation coverage for src/
    src_dir = 'src'

    if not os.path.exists(src_dir):
        sys.exit(0)

    total_functions = 0
    documented_functions = 0

    for root, dirs, files in os.walk(src_dir):
        # Skip test files
        dirs[:] = [d for d in dirs if d not in ['__tests__', 'test', 'tests']]

        for file in files:
            if file.endswith(('.py', '.ts', '.tsx', '.js', '.jsx')):
                file_path = os.path.join(root, file)
                total_functions += count_functions(file_path)
                documented_functions += count_documented_functions(file_path)

    if total_functions > 0:
        coverage = (documented_functions / total_functions) * 100

        print(f"\n📊 Documentation Coverage Report")
        print(f"Documented functions: {documented_functions}/{total_functions}")
        print(f"Coverage: {coverage:.1f}%")

        if coverage < 60:
            print("\n⚠️ Documentation coverage is low")
            print("Consider adding documentation to public APIs")
        elif coverage < 80:
            print("\n✓ Documentation coverage is good, but could be better")
        else:
            print("\n✓ Excellent documentation coverage!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

    sys.exit(0)
chmod +x .factory/hooks/docs-coverage.py
Run on session end:
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/docs-coverage.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
​
Best practices
1
Automate but don't auto-commit

Generate docs but let users review before committing:
# Generate docs
typedoc --out docs/api src/

# Alert but don't commit
echo "✓ API docs regenerated at docs/api"
echo "Review changes: git diff docs/"
2
Keep doc examples testable

Extract examples from actual tests:
# Extract example from test file
sed -n '/Example:/,/End example/p' Button.test.tsx > docs/examples/button.md
3
Version documentation

Tag docs with version info:
# API Reference

> Version: 2.1.0
> Last updated: 2024-01-15
4
Link docs to code

Include source file references:
## Button Component

Source: [`src/components/Button.tsx`](../src/components/Button.tsx)
5
Use doc generation tools

Don’t manually maintain API docs:
# TypeScript
typedoc --out docs/api src/

# Python
pdoc --html --output-dir docs/api src/

# Go
godoc -http=:6060
​
Troubleshooting
Problem: Can’t generate documentation
Solution: Check tool configuration:
# Verify tool installation
which typedoc

# Check config file
cat typedoc.json

# Test manually
typedoc --version
typedoc --help
Problem: Doc examples don’t match code
Solution: Extract examples from tests:
// In test file
/* DOC_EXAMPLE_START: basic-usage */
const result = myFunction(input);
expect(result).toBe(expected);
/* DOC_EXAMPLE_END */
Then extract programmatically:
sed -n '/DOC_EXAMPLE_START/,/DOC_EXAMPLE_END/p' test.ts
Problem: Doc generation takes too long
Solution: Build incrementally:
# Only rebuild changed files
typedoc --incremental src/

# Or skip in hooks, run manually
if [ "$SKIP_DOC_BUILD" = "true" ]; then
  exit 0
fi


Hooks
Git Workflow Hooks

Copy page

Integrate hooks with Git for commit validation, branch protection, and automated workflows

This cookbook shows how to use hooks to enforce Git workflows, validate commits, protect branches, and automate changelog generation.
​
How it works
Git workflow hooks can:
Validate commits: Check commit messages follow conventions
Protect branches: Prevent accidental commits to main/production
Generate changelogs: Auto-create changelog entries from commits
Run pre-push checks: Validate code before pushing
Enforce PR requirements: Check branch names, linear issues, etc.
​
Prerequisites
Basic Git tools:

Git

GitHub CLI (optional)

Conventional Commits (optional)
git --version
​
Basic Git hooks
​
Commit message validation
Enforce conventional commit format.
Create .factory/hooks/validate-commit-msg.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')

# Only validate Bash commands that look like git commit
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

command=$(echo "$input" | jq -r '.tool_input.command')

# Check if this is a git commit command
if ! echo "$command" | grep -qE "^git commit"; then
  exit 0
fi

# Extract commit message from command
if echo "$command" | grep -qE "git commit -m"; then
  # Extract message from -m flag
  commit_msg=$(echo "$command" | sed -E 's/.*git commit.*-m[= ]*["\x27]([^"\x27]+)["\x27].*/\1/')
else
  # Allow commits without -m (will open editor)
  exit 0
fi

# Validate conventional commit format
# Format: type(scope): description
# Example: feat(auth): add login functionality

if ! echo "$commit_msg" | grep -qE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?:.+"; then
  echo "❌ Invalid commit message format" >&2
  echo "" >&2
  echo "Commit message must follow Conventional Commits format:" >&2
  echo "  type(scope): description" >&2
  echo "" >&2
  echo "Valid types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  feat(auth): add user login" >&2
  echo "  fix(api): handle null values" >&2
  echo "  docs: update README" >&2
  exit 2
fi

# Check for Linear issue reference
if ! echo "$commit_msg" | grep -qE "FAC-[0-9]+"; then
  echo "⚠️ No Linear issue reference found" >&2
  echo "Consider adding issue reference like: feat(auth): add login FAC-123" >&2
  # Warning only, don't block
fi

exit 0
chmod +x .factory/hooks/validate-commit-msg.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/validate-commit-msg.sh",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
​
Branch protection
Prevent commits directly to protected branches.
Create .factory/hooks/protect-branches.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only check git commit commands
if [ "$tool_name" != "Bash" ] || ! echo "$command" | grep -qE "^git (commit|push)"; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Check if we're in a git repo
if [ ! -d ".git" ]; then
  exit 0
fi

current_branch=$(git branch --show-current)

# Protected branches that cannot be committed to directly
protected_branches=("main" "master" "production" "prod")

for branch in "${protected_branches[@]}"; do
  if [ "$current_branch" = "$branch" ]; then
    echo "❌ Cannot commit directly to protected branch: $branch" >&2
    echo "" >&2
    echo "Please create a feature branch instead:" >&2
    echo "  git checkout -b feature/your-feature-name" >&2
    echo "" >&2
    echo "Then create a pull request to merge your changes." >&2
    exit 2
  fi
done

exit 0
chmod +x .factory/hooks/protect-branches.sh
​
Enforce branch naming
Require feature branches to follow naming conventions:
Create .factory/hooks/validate-branch-name.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only check git checkout -b commands
if [ "$tool_name" != "Bash" ] || ! echo "$command" | grep -qE "^git checkout -b"; then
  exit 0
fi

# Extract branch name
branch_name=$(echo "$command" | sed -E 's/.*git checkout -b[= ]*([^ ]+).*/\1/')

# Valid patterns:
# - feature/FAC-123-description
# - fix/FAC-123-description
# - hotfix/FAC-123-description

if ! echo "$branch_name" | grep -qE "^(feature|fix|hotfix|docs|refactor)/[A-Z]+-[0-9]+-[a-z0-9-]+$"; then
  echo "❌ Invalid branch name format" >&2
  echo "" >&2
  echo "Branch names must follow the pattern:" >&2
  echo "  type/ISSUE-123-description" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  feature/FAC-123-add-user-auth" >&2
  echo "  fix/FAC-456-fix-login-bug" >&2
  echo "  hotfix/FAC-789-critical-security-fix" >&2
  exit 2
fi

exit 0
chmod +x .factory/hooks/validate-branch-name.sh
​
Advanced Git automation
​
Auto-generate changelog entries
Automatically create changelog entries from commits:
Create .factory/hooks/update-changelog.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only run after git commit
if [ "$tool_name" != "Bash" ] || ! echo "$command" | grep -qE "^git commit"; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Get the last commit message
last_commit=$(git log -1 --pretty=format:"%s")

# Parse conventional commit
if echo "$last_commit" | grep -qE "^(feat|fix)(\(.+\))?:"; then
  commit_type=$(echo "$last_commit" | sed -E 's/^([^:(]+).*/\1/')
  commit_msg=$(echo "$last_commit" | sed -E 's/^[^:]+: (.+)/\1/')

  # Determine changelog section
  if [ "$commit_type" = "feat" ]; then
    section="### Features"
  elif [ "$commit_type" = "fix" ]; then
    section="### Bug Fixes"
  else
    exit 0
  fi

  # Create/update CHANGELOG.md
  if [ ! -f "CHANGELOG.md" ]; then
    cat > CHANGELOG.md << EOF
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

$section

- $commit_msg

EOF
  else
    # Insert into Unreleased section
    if grep -q "## \[Unreleased\]" CHANGELOG.md; then
      # Check if section exists
      if grep -q "^$section" CHANGELOG.md; then
        # Add to existing section
        sed -i.bak "/^$section/a\\
- $commit_msg
" CHANGELOG.md
      else
        # Create new section
        sed -i.bak "/## \[Unreleased\]/a\\
\\
$section\\
\\
- $commit_msg
" CHANGELOG.md
      fi
      rm CHANGELOG.md.bak 2>/dev/null || true
    fi
  fi

  echo "✓ Updated CHANGELOG.md"
fi

exit 0
chmod +x .factory/hooks/update-changelog.sh
Add to PostToolUse:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/update-changelog.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
​
Pre-push validation
Run tests and checks before allowing git push:
Create .factory/hooks/pre-push-check.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only check git push commands
if [ "$tool_name" != "Bash" ] || ! echo "$command" | grep -qE "^git push"; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "🔍 Running pre-push checks..."

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
  echo "⚠️ You have uncommitted changes" >&2
  echo "Commit or stash them before pushing" >&2
  git status --short >&2
  exit 2
fi

# Run linter
if [ -f "package.json" ] && grep -q '"lint"' package.json; then
  echo "Running linter..."
  if ! npm run lint 2>&1; then
    echo "❌ Linting failed" >&2
    echo "Fix lint errors before pushing" >&2
    exit 2
  fi
  echo "✓ Linting passed"
fi

# Run tests
if [ -f "package.json" ] && grep -q '"test"' package.json; then
  echo "Running tests..."
  if ! npm test 2>&1; then
    echo "❌ Tests failed" >&2
    echo "Fix failing tests before pushing" >&2
    exit 2
  fi
  echo "✓ Tests passed"
fi

# Check for merge conflicts markers
if git grep -qE "^(<<<<<<<|=======|>>>>>>>)" 2>/dev/null; then
  echo "❌ Merge conflict markers found in files" >&2
  git grep -l "^(<<<<<<<|=======|>>>>>>>)" >&2
  exit 2
fi

echo "✓ All pre-push checks passed"

exit 0
chmod +x .factory/hooks/pre-push-check.sh
​
Auto-create PR when pushing new branch
Automatically open a PR when pushing a feature branch:
Create .factory/hooks/auto-create-pr.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only run after successful git push of a new branch
if [ "$tool_name" != "Bash" ] || ! echo "$command" | grep -qE "^git push.*-u origin"; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
  exit 0
fi

current_branch=$(git branch --show-current)

# Don't create PR for main/master branches
if [[ "$current_branch" =~ ^(main|master|dev|develop)$ ]]; then
  exit 0
fi

# Check if PR already exists
if gh pr view &>/dev/null; then
  echo "ℹ️ PR already exists for this branch"
  exit 0
fi

# Extract issue number from branch name
issue_number=""
if [[ $current_branch =~ ([A-Z]+-[0-9]+) ]]; then
  issue_number="${BASH_REMATCH[1]}"
fi

# Generate PR title from branch name or commits
pr_title="$current_branch"
if [ -n "$issue_number" ]; then
  pr_title="$issue_number: $(echo "$current_branch" | sed -E 's/^[^/]+\/[A-Z]+-[0-9]+-//; s/-/ /g')"
fi

# Create PR
echo "🔄 Creating pull request..."
if gh pr create --title "$pr_title" --body "Closes $issue_number" --web; then
  echo "✓ Pull request created and opened in browser"
else
  echo "⚠️ Could not create PR automatically"
fi

exit 0
chmod +x .factory/hooks/auto-create-pr.sh
​
Enforce co-authorship in commits
Add co-author trailers to commits:
Create .factory/hooks/add-coauthor.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only modify git commit commands
if [ "$tool_name" != "Bash" ] || ! echo "$command" | grep -qE "^git commit.*-m"; then
  exit 0
fi

# Extract commit message
commit_msg=$(echo "$command" | sed -E 's/.*git commit.*-m[= ]*["\x27]([^"\x27]+)["\x27].*/\1/')

# Check if co-author is already present
if echo "$commit_msg" | grep -qE "Co-authored-by:"; then
  exit 0
fi

# Add factory droid co-author
coauthor="Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"

# Modify command to include co-author
modified_msg="$commit_msg

$coauthor"

# Return modified command via JSON output
cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Adding co-author to commit",
    "updatedInput": {
      "command": "$(echo "$command" | sed -E "s/(git commit.*-m[= ]*)[\"']([^\"']+)[\"']/\1\"$modified_msg\"/")"
    }
  }
}
EOF

exit 0
chmod +x .factory/hooks/add-coauthor.sh
​
Real-world examples
​
Example 1: Monorepo commit validation
Ensure commits only touch one package:
Create .factory/hooks/validate-monorepo-scope.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

if [ "$tool_name" != "Bash" ] || ! echo "$command" | grep -qE "^git commit"; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Get staged files
staged_files=$(git diff --cached --name-only)

if [ -z "$staged_files" ]; then
  exit 0
fi

# Check if changes span multiple packages
packages=$(echo "$staged_files" | grep -E "^(packages|apps)/" | cut -d/ -f1-2 | sort -u)
package_count=$(echo "$packages" | wc -l | tr -d ' ')

if [ "$package_count" -gt 1 ]; then
  echo "❌ Commit spans multiple packages" >&2
  echo "" >&2
  echo "Changed packages:" >&2
  echo "$packages" | sed 's/^/  - /' >&2
  echo "" >&2
  echo "Please commit changes to each package separately for clearer history." >&2
  exit 2
fi

exit 0
​
Example 2: Release automation
Auto-tag releases when version changes:
Create .factory/hooks/auto-tag-release.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')

# Only run after commits
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

command=$(echo "$input" | jq -r '.tool_input.command // ""')
if ! echo "$command" | grep -qE "^git commit"; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Check if package.json version changed in last commit
if ! git diff HEAD~1 HEAD --name-only | grep -q "package.json"; then
  exit 0
fi

# Check if version field changed
if git diff HEAD~1 HEAD -- package.json | grep -q "^+.*\"version\""; then
  # Get new version
  new_version=$(jq -r '.version' package.json)

  echo "📦 Version bump detected: v$new_version"
  echo "Creating git tag..."

  # Create and push tag
  if git tag "v$new_version" && git push origin "v$new_version"; then
    echo "✓ Created and pushed tag v$new_version"
  fi
fi

exit 0
​
Best practices
1
Use PreToolUse for prevention

Block bad commits before they happen:
# In PreToolUse hook
if invalid_commit; then
  echo "❌ Cannot proceed" >&2
  exit 2  # Blocks the git commit
fi
2
Use PostToolUse for automation

Automate followup actions after successful commits:
# In PostToolUse hook
if git_commit_successful; then
  update_changelog
  create_pr
fi
3
Provide clear error messages

Tell users exactly what’s wrong and how to fix it:
echo "❌ Commit message must include issue reference" >&2
echo "Example: feat(auth): add login FAC-123" >&2
4
Make hooks configurable

Allow teams to customize behavior:
PROTECTED_BRANCHES="${DROID_PROTECTED_BRANCHES:-main,master,production}"
REQUIRE_ISSUE_REF="${DROID_REQUIRE_ISSUE:-true}"
5
Test hooks with dry-run

Test without making actual commits:
# Simulate a commit
echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m \"test\""}}' | \
  .factory/hooks/validate-commit-msg.sh
​
Troubleshooting
Problem: Validation too strict
Solution: Add escape hatches:
# Allow bypass with special prefix
if echo "$commit_msg" | grep -q "^WIP:"; then
  echo "⚠️ WIP commit allowed"
  exit 0
fi
Problem: Both Droid hooks and .git/hooks running
Solution: Coordinate or choose one:
# In .git/hooks/pre-commit
if [ -n "$DROID_SESSION" ]; then
  exit 0  # Let Droid hooks handle it
fi
Problem: Tests take too long
Solution: Run quick checks only:
# Run fast subset of tests
npm run test:unit  # Skip slow integration tests

# Or run in parallel with push
npm test &
git push

Hooks
Logging and Analytics

Copy page

Track Droid usage, collect metrics, and analyze development patterns with hooks

This cookbook shows how to use hooks to track Droid usage, collect development metrics, analyze patterns, and generate insights about your development workflow.
​
How it works
Logging and analytics hooks can:
Track tool usage: Log which tools Droid uses most frequently
Measure performance: Track session duration, command execution time
Analyze patterns: Identify common workflows and bottlenecks
Generate reports: Create usage summaries and insights
Monitor costs: Track token usage and API costs
​
Prerequisites
Tools for logging and data collection:

Basic tools

Optional analytics
# jq for JSON processing
brew install jq  # macOS
sudo apt-get install jq  # Ubuntu/Debian

# SQLite for local database
brew install sqlite3  # macOS (usually pre-installed)
​
Basic logging
​
Log all commands
Track every command Droid executes.
Create .factory/hooks/log-commands.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')

# Only log Bash commands
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

command=$(echo "$input" | jq -r '.tool_input.command')
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
session_id=$(echo "$input" | jq -r '.session_id')

# Log to file
log_file="$HOME/.factory/command-log.jsonl"

# Create log entry
log_entry=$(jq -n \
  --arg ts "$timestamp" \
  --arg sid "$session_id" \
  --arg cmd "$command" \
  '{timestamp: $ts, session_id: $sid, command: $cmd}')

echo "$log_entry" >> "$log_file"

exit 0
chmod +x .factory/hooks/log-commands.sh
Add to ~/.factory/settings.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/log-commands.sh",
            "timeout": 2
          }
        ]
      }
    ]
  }
}
Analyze logs:
# Most common commands
jq -r '.command' ~/.factory/command-log.jsonl | sort | uniq -c | sort -rn | head -10

# Commands by session
jq -r '"\(.session_id): \(.command)"' ~/.factory/command-log.jsonl
​
Track file modifications
Log all file edits and writes.
Create .factory/hooks/track-file-changes.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only track file operations
if [ "$tool_name" != "Write" ] && [ "$tool_name" != "Edit" ]; then
  exit 0
fi

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
session_id=$(echo "$input" | jq -r '.session_id')
cwd=$(echo "$input" | jq -r '.cwd')

# Determine file type
file_ext="${file_path##*.}"

# Calculate file size (for Write operations)
if [ "$tool_name" = "Write" ]; then
  content=$(echo "$input" | jq -r '.tool_input.content // ""')
  size=$(echo "$content" | wc -c | tr -d ' ')
else
  size="unknown"
fi

# Log to SQLite database
db_file="$HOME/.factory/file-changes.db"

# Create table if not exists
sqlite3 "$db_file" "CREATE TABLE IF NOT EXISTS file_changes (
  timestamp TEXT,
  session_id TEXT,
  project TEXT,
  operation TEXT,
  file_path TEXT,
  file_type TEXT,
  size INTEGER
);" 2>/dev/null

# Insert record
sqlite3 "$db_file" "INSERT INTO file_changes VALUES (
  '$timestamp',
  '$session_id',
  '$(basename "$cwd")',
  '$tool_name',
  '$file_path',
  '$file_ext',
  '$size'
);" 2>/dev/null

exit 0
chmod +x .factory/hooks/track-file-changes.sh
Query the database:
# Most edited files
sqlite3 ~/.factory/file-changes.db \
  "SELECT file_path, COUNT(*) as edits FROM file_changes
   GROUP BY file_path ORDER BY edits DESC LIMIT 10;"

# Files edited by type
sqlite3 ~/.factory/file-changes.db \
  "SELECT file_type, COUNT(*) as count FROM file_changes
   GROUP BY file_type ORDER BY count DESC;"

# Activity by project
sqlite3 ~/.factory/file-changes.db \
  "SELECT project, COUNT(*) as changes FROM file_changes
   GROUP BY project ORDER BY changes DESC;"
​
Session duration tracking
Measure how long sessions last:
Create .factory/hooks/track-session.sh:
#!/bin/bash

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')
session_id=$(echo "$input" | jq -r '.session_id')

db_file="$HOME/.factory/sessions.db"

# Create table
sqlite3 "$db_file" "CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  start_time TEXT,
  end_time TEXT,
  reason TEXT,
  duration_seconds INTEGER
);" 2>/dev/null

case "$hook_event" in
  "SessionStart")
    # Record session start
    start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    sqlite3 "$db_file" "INSERT OR REPLACE INTO sessions (session_id, start_time)
      VALUES ('$session_id', '$start_time');" 2>/dev/null
    ;;

  "SessionEnd")
    # Record session end and calculate duration
    end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    reason=$(echo "$input" | jq -r '.reason')

    # Get start time
    start_time=$(sqlite3 "$db_file" \
      "SELECT start_time FROM sessions WHERE session_id='$session_id';" 2>/dev/null)

    if [ -n "$start_time" ]; then
      # Calculate duration in seconds
      start_epoch=$(date -jf "%Y-%m-%dT%H:%M:%SZ" "$start_time" +%s 2>/dev/null || date -d "$start_time" +%s)
      end_epoch=$(date -jf "%Y-%m-%dT%H:%M:%SZ" "$end_time" +%s 2>/dev/null || date -d "$end_time" +%s)
      duration=$((end_epoch - start_epoch))

      # Update record
      sqlite3 "$db_file" "UPDATE sessions
        SET end_time='$end_time', reason='$reason', duration_seconds=$duration
        WHERE session_id='$session_id';" 2>/dev/null

      # Print summary
      echo "📊 Session duration: $((duration / 60)) minutes $((duration % 60)) seconds"
    fi
    ;;
esac

exit 0
chmod +x .factory/hooks/track-session.sh
Add to hooks:
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/track-session.sh",
            "timeout": 2
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/track-session.sh",
            "timeout": 2
          }
        ]
      }
    ]
  }
}
Query session stats:
# Average session duration
sqlite3 ~/.factory/sessions.db \
  "SELECT AVG(duration_seconds) / 60.0 as avg_minutes FROM sessions
   WHERE duration_seconds IS NOT NULL;"

# Sessions by exit reason
sqlite3 ~/.factory/sessions.db \
  "SELECT reason, COUNT(*) as count FROM sessions
   GROUP BY reason ORDER BY count DESC;"

# Longest sessions
sqlite3 ~/.factory/sessions.db \
  "SELECT session_id, duration_seconds / 60.0 as minutes FROM sessions
   ORDER BY duration_seconds DESC LIMIT 10;"
​
Advanced analytics
​
Usage heatmap
Track when Droid is used most:
Create .factory/hooks/usage-heatmap.py:
#!/usr/bin/env python3
"""
Generate usage heatmap showing when Droid is used most.
"""
import json
import sys
import sqlite3
from datetime import datetime
from collections import defaultdict

def generate_heatmap():
    """Create a heatmap of Droid usage by hour and day."""
    db_path = os.path.expanduser('~/.factory/sessions.db')

    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all session starts
    cursor.execute("SELECT start_time FROM sessions WHERE start_time IS NOT NULL")

    # Count by day of week and hour
    heatmap = defaultdict(lambda: defaultdict(int))

    for (start_time,) in cursor.fetchall():
        try:
            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            day = dt.strftime('%A')
            hour = dt.hour
            heatmap[day][hour] += 1
        except:
            continue

    conn.close()

    # Print heatmap
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    hours = range(24)

    print("\n📊 Droid Usage Heatmap")
    print("=" * 80)
    print(f"{'Day':<12} {'Morning (6-12)':<15} {'Afternoon (12-18)':<15} {'Evening (18-24)':<15}")
    print("-" * 80)

    for day in days:
        morning = sum(heatmap[day][h] for h in range(6, 12))
        afternoon = sum(heatmap[day][h] for h in range(12, 18))
        evening = sum(heatmap[day][h] for h in range(18, 24))

        print(f"{day:<12} {morning:<15} {afternoon:<15} {evening:<15}")

    print("=" * 80)

if __name__ == '__main__':
    import os
    generate_heatmap()
chmod +x .factory/hooks/usage-heatmap.py
Run periodically:
# Add to weekly report
~/.factory/hooks/usage-heatmap.py
​
Tool usage statistics
Track which tools are used most:
Create .factory/hooks/tool-stats.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')

# Log tool usage
log_file="$HOME/.factory/tool-usage.log"
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "$timestamp $tool_name" >> "$log_file"

exit 0
chmod +x .factory/hooks/tool-stats.sh
Add to PreToolUse for all tools:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/tool-stats.sh",
            "timeout": 1
          }
        ]
      }
    ]
  }
}
Generate report:
# Most used tools
awk '{print $2}' ~/.factory/tool-usage.log | sort | uniq -c | sort -rn

# Tool usage over time
awk '{print $1}' ~/.factory/tool-usage.log | cut -d'T' -f1 | uniq -c

# Usage by hour
awk '{print $1}' ~/.factory/tool-usage.log | cut -d'T' -f2 | cut -d':' -f1 | sort | uniq -c
​
Performance metrics
Track hook execution performance:
Create .factory/hooks/perf-monitor.sh:
#!/bin/bash

# This hook measures its own performance and logs it
start_time=$(date +%s.%N)

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')
tool_name=$(echo "$input" | jq -r '.tool_name // "none"')

# Simulate your actual hook work here
# ...

end_time=$(date +%s.%N)
duration=$(echo "$end_time - $start_time" | bc)

# Log performance
perf_log="$HOME/.factory/hook-performance.log"
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "$timestamp $hook_event $tool_name ${duration}s" >> "$perf_log"

# Warn if hook is slow
if (( $(echo "$duration > 1.0" | bc -l) )); then
  echo "⚠️ Hook took ${duration}s to execute (>1s threshold)" >&2
fi

exit 0
Analyze performance:
# Slowest hooks
sort -k4 -rn ~/.factory/hook-performance.log | head -10

# Average execution time by event
awk '{sum[$2]+=$4; count[$2]++} END {for (event in sum) print event, sum[event]/count[event] "s"}' \
  ~/.factory/hook-performance.log
​
Cost tracking
Monitor token usage and API costs:
Create .factory/hooks/track-costs.sh:
#!/bin/bash

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')

# Only track on session end
if [ "$hook_event" != "SessionEnd" ]; then
  exit 0
fi

session_id=$(echo "$input" | jq -r '.session_id')
transcript_path=$(echo "$input" | jq -r '.transcript_path')

# Parse transcript for token usage
if [ ! -f "$transcript_path" ]; then
  exit 0
fi

# Extract token counts from transcript (simplified)
# In reality, you'd parse the actual transcript format
input_tokens=$(grep -o '"input_tokens":[0-9]*' "$transcript_path" | \
  cut -d':' -f2 | paste -sd+ - | bc)
output_tokens=$(grep -o '"output_tokens":[0-9]*' "$transcript_path" | \
  cut -d':' -f2 | paste -sd+ - | bc)

# Calculate approximate cost (rates vary by model)
# Claude Sonnet 4.5: $3 per 1M input, $15 per 1M output
input_cost=$(echo "scale=4; $input_tokens * 3 / 1000000" | bc)
output_cost=$(echo "scale=4; $output_tokens * 15 / 1000000" | bc)
total_cost=$(echo "scale=4; $input_cost + $output_cost" | bc)

# Log costs
cost_db="$HOME/.factory/costs.db"

sqlite3 "$cost_db" "CREATE TABLE IF NOT EXISTS costs (
  session_id TEXT PRIMARY KEY,
  timestamp TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  total_cost REAL
);" 2>/dev/null

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

sqlite3 "$cost_db" "INSERT OR REPLACE INTO costs VALUES (
  '$session_id',
  '$timestamp',
  $input_tokens,
  $output_tokens,
  $total_cost
);" 2>/dev/null

# Print summary
echo "💰 Session cost: \$${total_cost} (${input_tokens} input + ${output_tokens} output tokens)"

exit 0
chmod +x .factory/hooks/track-costs.sh
Query costs:
# Total costs
sqlite3 ~/.factory/costs.db \
  "SELECT SUM(total_cost) as total FROM costs;"

# Cost by date
sqlite3 ~/.factory/costs.db \
  "SELECT DATE(timestamp) as date, SUM(total_cost) as cost
   FROM costs GROUP BY DATE(timestamp) ORDER BY date DESC;"

# Most expensive sessions
sqlite3 ~/.factory/costs.db \
  "SELECT session_id, total_cost FROM costs
   ORDER BY total_cost DESC LIMIT 10;"
​
Generate weekly reports
Compile usage reports:
Create .factory/hooks/weekly-report.py:
#!/usr/bin/env python3
"""
Generate weekly usage report.
"""
import os
import sqlite3
from datetime import datetime, timedelta

def generate_report():
    """Generate comprehensive weekly report."""
    home = os.path.expanduser('~')
    sessions_db = f"{home}/.factory/sessions.db"
    files_db = f"{home}/.factory/file-changes.db"
    costs_db = f"{home}/.factory/costs.db"

    # Get date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    print(f"\n{'='*60}")
    print(f"Droid Weekly Report")
    print(f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")

    # Session statistics
    if os.path.exists(sessions_db):
        conn = sqlite3.connect(sessions_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*), AVG(duration_seconds), SUM(duration_seconds)
            FROM sessions
            WHERE start_time >= ?
        """, (start_date.isoformat(),))

        count, avg_duration, total_duration = cursor.fetchone()

        if count:
            print("📊 Session Statistics")
            print(f"  Total sessions: {count}")
            print(f"  Average duration: {int(avg_duration / 60)} minutes")
            print(f"  Total time: {int(total_duration / 3600)} hours")
            print()

        conn.close()

    # File changes
    if os.path.exists(files_db):
        conn = sqlite3.connect(files_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_type, COUNT(*) as changes
            FROM file_changes
            WHERE timestamp >= ?
            GROUP BY file_type
            ORDER BY changes DESC
            LIMIT 5
        """, (start_date.isoformat(),))

        print("📝 Most Edited File Types")
        for file_type, changes in cursor.fetchall():
            print(f"  .{file_type}: {changes} changes")
        print()

        conn.close()

    # Costs
    if os.path.exists(costs_db):
        conn = sqlite3.connect(costs_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT SUM(total_cost), SUM(input_tokens), SUM(output_tokens)
            FROM costs
            WHERE timestamp >= ?
        """, (start_date.isoformat(),))

        total_cost, input_tokens, output_tokens = cursor.fetchone()

        if total_cost:
            print("💰 Cost Summary")
            print(f"  Total cost: ${total_cost:.2f}")
            print(f"  Input tokens: {input_tokens:,}")
            print(f"  Output tokens: {output_tokens:,}")
            print()

        conn.close()

    print(f"{'='*60}\n")

if __name__ == '__main__':
    generate_report()
chmod +x .factory/hooks/weekly-report.py
Schedule weekly:
# Add to crontab
# Run every Monday at 9am
# 0 9 * * 1 ~/.factory/hooks/weekly-report.py
​
Best practices
1
Use structured logging

Log in JSON or to database for easy querying:
# JSON logs
jq -n --arg cmd "$command" '{timestamp: now, command: $cmd}' >> log.jsonl

# SQLite for analytics
sqlite3 db.db "INSERT INTO logs VALUES (...)"
2
Minimize performance impact

Keep logging hooks fast:
# Async logging
(echo "$log_entry" >> log.json) &

# Batch writes
echo "$entry" >> /tmp/buffer
if [ $(wc -l < /tmp/buffer) -gt 100 ]; then
  cat /tmp/buffer >> permanent.log
  > /tmp/buffer
fi
3
Protect sensitive data

Don’t log secrets or credentials:
# Redact sensitive info
command=$(echo "$command" | sed 's/password=[^ ]*/password=***/g')
4
Rotate logs

Prevent log files from growing too large:
# Log rotation
if [ $(du -k log.json | cut -f1) -gt 10240 ]; then  # 10MB
  mv log.json log.json.$(date +%Y%m%d)
  gzip log.json.*
fi
5
Make analytics opt-in

Respect user privacy:
if [ "$DROID_ANALYTICS_ENABLED" != "true" ]; then
  exit 0
fi
​
Troubleshooting
Problem: Log files consuming too much disk space
Solution: Implement log rotation:
# Compress old logs
find ~/.factory -name "*.log" -mtime +7 -exec gzip {} \;

# Delete very old logs
find ~/.factory -name "*.log.gz" -mtime +30 -delete
Problem: SQLite database locked during concurrent access
Solution: Use WAL mode and retry logic:
# Enable WAL mode
sqlite3 db.db "PRAGMA journal_mode=WAL;"

# Retry on busy
sqlite3 db.db -cmd ".timeout 5000" "INSERT ..."
Problem: Hooks take too long
Solution: Use async logging:
# Background logging
(
  # Expensive logging operation
  process_and_log_data
) &  # Run in background

exit 0  # Return immediately
​

Hooks
Custom Notifications

Copy page

Get notified when Droid needs attention using desktop alerts, sounds, Slack, and more

This cookbook shows how to set up custom notifications so you know when Droid needs your input or when important events occur during a session.
​
How it works
Notification hooks can:
Trigger on multiple events: Notification, Stop, SubagentStop, SessionEnd
Support multiple channels: Desktop notifications, system sounds, Slack, email, webhooks
Provide context: Include session details, task completion status, error messages
Filter intelligently: Only notify on important events
Work cross-platform: macOS, Linux, Windows
​
Prerequisites
Install notification tools for your platform:

macOS

Linux

Windows (PowerShell)
# Built-in commands (no installation needed)
which osascript  # For display notifications
which afplay     # For sounds
For Slack notifications, create a webhook at api.slack.com/messaging/webhooks.
​
Basic notifications
​
Desktop notification when Droid waits
Get notified when Droid is waiting for your input.
Create .factory/hooks/notify-wait.sh:
#!/bin/bash

input=$(cat)
message=$(echo "$input" | jq -r '.message // "Droid needs your attention"')
hook_event=$(echo "$input" | jq -r '.hook_event_name')

# Only notify on actual wait events
if [ "$hook_event" != "Notification" ]; then
  exit 0
fi

# Platform-specific notification
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  osascript -e "display notification \"$message\" with title \"Droid\" sound name \"Ping\""
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  # Linux
  notify-send "Droid" "$message" -i dialog-information -u normal
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
  # Windows
  powershell -Command "New-BurntToastNotification -Text 'Droid', '$message'"
fi

exit 0
chmod +x .factory/hooks/notify-wait.sh
Add to ~/.factory/settings.json (user-wide):
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/notify-wait.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
​
Sound alert when task completes
Play a sound when Droid finishes.
Create .factory/hooks/completion-sound.sh:
#!/bin/bash

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')

# Only alert on completion events
if [ "$hook_event" != "Stop" ]; then
  exit 0
fi

# Platform-specific sound
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS - use system sounds
  afplay /System/Library/Sounds/Glass.aiff
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  # Linux - use system bell or speaker-test
  paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null || \
    echo -e '\a'  # Fallback to terminal bell
fi

exit 0
chmod +x .factory/hooks/completion-sound.sh
Add to ~/.factory/settings.json:
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/completion-sound.sh",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
​
Advanced notifications
​
Slack integration
Send Slack messages when Droid completes tasks.
Create .factory/hooks/slack-notify.sh:
#!/bin/bash
set -e

# Configure your Slack webhook URL
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

if [ -z "$SLACK_WEBHOOK_URL" ]; then
  echo "SLACK_WEBHOOK_URL not set, skipping Slack notification"
  exit 0
fi

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')
session_id=$(echo "$input" | jq -r '.session_id')
cwd=$(echo "$input" | jq -r '.cwd')

# Build message based on event type
case "$hook_event" in
  "Stop")
    title="✅ Droid Task Completed"
    color="good"
    ;;
  "SessionEnd")
    title="🏁 Droid Session Ended"
    color="#808080"
    reason=$(echo "$input" | jq -r '.reason')
    ;;
  "SubagentStop")
    title="🤖 Subagent Task Completed"
    color="good"
    ;;
  *)
    exit 0
    ;;
esac

# Send to Slack
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d @- << EOF
{
  "attachments": [
    {
      "color": "$color",
      "title": "$title",
      "fields": [
        {
          "title": "Project",
          "value": "$(basename "$cwd")",
          "short": true
        },
        {
          "title": "Session",
          "value": "${session_id:0:8}...",
          "short": true
        }
      ],
      "footer": "Droids",
      "ts": $(date +%s)
    }
  ]
}
EOF

exit 0
chmod +x .factory/hooks/slack-notify.sh
Set your webhook URL:
# Add to ~/.bashrc or ~/.zshrc
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
Add to ~/.factory/settings.json:
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/slack-notify.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.factory/hooks/slack-notify.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
​
Email notifications
Send email alerts for important events.
Create .factory/hooks/email-notify.sh:
#!/bin/bash
set -e

# Configure email settings
EMAIL_TO="${DROID_NOTIFY_EMAIL:-your-email@example.com}"
EMAIL_FROM="${DROID_FROM_EMAIL:-droid@factory.ai}"

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')

# Only notify on session end with errors
if [ "$hook_event" != "SessionEnd" ]; then
  exit 0
fi

reason=$(echo "$input" | jq -r '.reason')
session_id=$(echo "$input" | jq -r '.session_id')
cwd=$(echo "$input" | jq -r '.cwd')

# Check if session ended due to error
if [ "$reason" != "error" ] && [ "$reason" != "other" ]; then
  exit 0
fi

# Send email using sendmail or mail command
subject="Droid Session Ended: $(basename "$cwd")"
body="Session $session_id ended with reason: $reason

Project: $cwd
Time: $(date)

Check the logs for more details."

# Try sendmail first, fallback to mail command
if command -v sendmail &> /dev/null; then
  echo -e "Subject: $subject\nFrom: $EMAIL_FROM\nTo: $EMAIL_TO\n\n$body" | sendmail -t
elif command -v mail &> /dev/null; then
  echo "$body" | mail -s "$subject" "$EMAIL_TO"
else
  echo "No email command available (sendmail or mail)"
  exit 1
fi

exit 0
chmod +x .factory/hooks/email-notify.sh
Configure environment:
# Add to ~/.bashrc or ~/.zshrc
export DROID_NOTIFY_EMAIL="your-email@example.com"
​
Rich desktop notifications with actions
macOS notifications with action buttons.
Create .factory/hooks/rich-notify-macos.sh:
#!/bin/bash

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')
message=$(echo "$input" | jq -r '.message // "Droid needs your attention"')
session_id=$(echo "$input" | jq -r '.session_id')

# Only for macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
  exit 0
fi

case "$hook_event" in
  "Notification")
    # Notification with action buttons
    osascript << EOF
tell application "System Events"
  display notification "$message" with title "Droid Waiting" subtitle "Session: ${session_id:0:8}" sound name "Ping"
end tell
EOF
    ;;

  "Stop")
    # Success notification
    osascript << EOF
tell application "System Events"
  display notification "Task completed successfully" with title "Droid Complete" subtitle "$(basename "$PWD")" sound name "Glass"
end tell
EOF
    ;;

  "SessionEnd")
    reason=$(echo "$input" | jq -r '.reason')
    # Different sound based on reason
    sound="Purr"
    if [ "$reason" == "error" ]; then
      sound="Basso"
    fi

    osascript << EOF
tell application "System Events"
  display notification "Session ended: $reason" with title "Droid Session" subtitle "$(basename "$PWD")" sound name "$sound"
end tell
EOF
    ;;
esac

exit 0
chmod +x .factory/hooks/rich-notify-macos.sh
​
Webhook integration
Send notifications to custom webhooks:
Create .factory/hooks/webhook-notify.sh:
#!/bin/bash
set -e

WEBHOOK_URL="${DROID_WEBHOOK_URL:-}"

if [ -z "$WEBHOOK_URL" ]; then
  exit 0
fi

input=$(cat)

# Forward the entire hook input to webhook
curl -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d "$input" \
  --max-time 5 \
  --silent \
  --show-error

exit 0
chmod +x .factory/hooks/webhook-notify.sh
export DROID_WEBHOOK_URL="https://your-webhook-url.com/droid-events"
​
Real-world examples
​
Example 1: Focus mode notifications
Only notify when you’re away from your desk:
Create .factory/hooks/smart-notify.sh:
#!/bin/bash

input=$(cat)

# Check if user is idle (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
  idle_time=$(ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF/1000000000)}')

  # Only notify if idle for more than 60 seconds
  if [ "$idle_time" -lt 60 ]; then
    exit 0
  fi
fi

# Send notification
message=$(echo "$input" | jq -r '.message // "Droid needs your attention"')
osascript -e "display notification \"$message\" with title \"Droid\" sound name \"Ping\""

exit 0
​
Example 2: Team notification dashboard
Log all events to a shared dashboard:
Create .factory/hooks/team-logger.sh:
#!/bin/bash
set -e

# Central logging endpoint
LOG_ENDPOINT="${TEAM_LOG_ENDPOINT:-}"

if [ -z "$LOG_ENDPOINT" ]; then
  exit 0
fi

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name')
session_id=$(echo "$input" | jq -r '.session_id')
cwd=$(echo "$input" | jq -r '.cwd')

# Add metadata
payload=$(echo "$input" | jq -c ". + {
  user: \"$USER\",
  hostname: \"$HOSTNAME\",
  timestamp: \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
  project: \"$(basename "$cwd")\"
}")

# Send to logging service
curl -X POST "$LOG_ENDPOINT" \
  -H 'Content-Type: application/json' \
  -d "$payload" \
  --max-time 3 \
  --silent

exit 0
​
Best practices
1
Keep notification scripts fast

Use short timeouts to avoid blocking Droid:
{
  "timeout": 5  // 5 seconds max for notifications
}
2
Handle failures gracefully

Don’t block execution if notifications fail:
# Continue even if curl fails
curl -X POST "$URL" ... || true
exit 0
3
Respect user preferences

Check environment variables for opt-out:
if [ "$DROID_DISABLE_NOTIFICATIONS" = "true" ]; then
  exit 0
fi
4
Test notifications

Manually trigger hooks for testing:
# Test notification script
echo '{"hook_event_name":"Notification","message":"Test"}' | .factory/hooks/notify-wait.sh
5
Use appropriate notification levels

Different events warrant different urgency:
Notification: High urgency (Droid waiting)
Stop: Medium urgency (task complete)
SessionEnd: Low urgency (FYI only)
​
Troubleshooting
Problem: No notifications show up
Solution: Check notification permissions:
# macOS - check System Settings > Notifications
# Linux - verify notify-send works
notify-send "Test" "This is a test"

# Check if hooks are executing
droid --debug
Problem: Slack messages not sending
Solution: Test webhook directly:
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test from curl"}'
Problem: Getting spammed with alerts
Solution: Add rate limiting:
# Only notify once every 5 minutes
LAST_NOTIFY_FILE="/tmp/droid-last-notify"

if [ -f "$LAST_NOTIFY_FILE" ]; then
  last_time=$(cat "$LAST_NOTIFY_FILE")
  current_time=$(date +%s)
  if [ $((current_time - last_time)) -lt 300 ]; then
    exit 0
  fi
fi

date +%s > "$LAST_NOTIFY_FILE"
# ... send notification
Problem: No audio alert
Solution: Check audio system:
# macOS - list available sounds
ls /System/Library/Sounds/

# Test sound
afplay /System/Library/Sounds/Glass.aiff

# Linux - check audio
paplay /usr/share/sounds/freedesktop/stereo/complete.oga
​

Session Automation

Copy page

Automate session setup with context loading, environment configuration, and dependency management

This cookbook shows how to use SessionStart hooks to automatically prepare your development environment when Droid starts, saving time and ensuring consistency.
​
How it works
SessionStart hooks:
Run at session start: Triggered when starting new sessions or resuming
Load context: Add relevant project information to the conversation
Setup environment: Configure paths, environment variables, tools
Check dependencies: Verify required tools and packages are available
Persist state: Set environment variables for the entire session
​
Prerequisites
Basic tools for automation:

macOS/Linux

Git/GitHub CLI
# jq for JSON processing
brew install jq  # macOS
sudo apt-get install jq  # Ubuntu/Debian
​
Basic session automation
​
Load project context
Automatically provide Droid with project information.
Create .factory/hooks/load-context.sh:
#!/bin/bash
set -e

input=$(cat)
source_type=$(echo "$input" | jq -r '.source')

# Only load context on startup and resume
if [ "$source_type" != "startup" ] && [ "$source_type" != "resume" ]; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "📋 Loading project context..."
echo ""

# Project overview
if [ -f "README.md" ]; then
  echo "## Project Overview"
  echo ""
  head -n 20 README.md
  echo ""
fi

# Recent git activity
if [ -d ".git" ]; then
  echo "## Recent Changes"
  echo ""
  echo "Latest commits:"
  git log --oneline -5
  echo ""

  echo "Current branch: $(git branch --show-current)"
  echo "Uncommitted changes: $(git status --short | wc -l | tr -d ' ') files"
  echo ""
fi

# Project structure
if [ -f "package.json" ]; then
  echo "## Package Info"
  echo ""
  echo "Name: $(jq -r '.name' package.json)"
  echo "Version: $(jq -r '.version' package.json)"
  echo ""

  echo "Scripts available:"
  jq -r '.scripts | keys[]' package.json | head -n 10 | sed 's/^/  - /'
  echo ""
fi

# TODO/FIXME comments
echo "## Open TODOs"
echo ""
echo "Found $(grep -r "TODO\|FIXME" src/ 2>/dev/null | wc -l | tr -d ' ') TODO/FIXME comments in src/"
echo ""

exit 0
chmod +x .factory/hooks/load-context.sh
Add to .factory/settings.json:
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/load-context.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
​
Setup development environment
Configure tools and paths automatically.
Create .factory/hooks/setup-env.sh:
#!/bin/bash
set -e

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "🔧 Setting up development environment..."

# Detect and setup Node.js version
if [ -f ".nvmrc" ] && command -v nvm &> /dev/null; then
  NODE_VERSION=$(cat .nvmrc)
  echo "📦 Switching to Node.js $NODE_VERSION"

  # Persist environment changes using DROID_ENV_FILE
  if [ -n "$DROID_ENV_FILE" ]; then
    # Capture environment before nvm
    ENV_BEFORE=$(export -p | sort)

    # Source nvm and switch version
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use

    # Capture changes and persist them
    ENV_AFTER=$(export -p | sort)
    comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$DROID_ENV_FILE"

    echo "✓ Node.js environment configured"
  fi
fi

# Setup Python virtual environment
if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
  if [ ! -d "venv" ]; then
    echo "⚠️ Virtual environment not found. Consider creating one:"
    echo "   python -m venv venv"
  else
    echo "🐍 Python virtual environment detected"

    if [ -n "$DROID_ENV_FILE" ]; then
      # Activate venv for session
      echo "source \"$cwd/venv/bin/activate\"" >> "$DROID_ENV_FILE"
      echo "✓ Virtual environment will be activated for Bash commands"
    fi
  fi
fi

# Add project binaries to PATH
if [ -d "node_modules/.bin" ] && [ -n "$DROID_ENV_FILE" ]; then
  echo "export PATH=\"\$PATH:$cwd/node_modules/.bin\"" >> "$DROID_ENV_FILE"
  echo "✓ Added node_modules/.bin to PATH"
fi

# Setup Go workspace
if [ -f "go.mod" ]; then
  echo "🔷 Go module detected"
  if [ -n "$DROID_ENV_FILE" ]; then
    echo "export GO111MODULE=on" >> "$DROID_ENV_FILE"
    echo "export GOPATH=$HOME/go" >> "$DROID_ENV_FILE"
  fi
fi

echo ""
echo "✓ Environment setup complete"

exit 0
chmod +x .factory/hooks/setup-env.sh
​
Advanced automation
​
Load recent Linear/GitHub issues
Provide Droid with context about current work.
Create .factory/hooks/load-issues.sh:
#!/bin/bash
set -e

input=$(cat)
source_type=$(echo "$input" | jq -r '.source')

if [ "$source_type" != "startup" ]; then
  exit 0
fi

echo "📋 Loading recent issues..."
echo ""

# Load GitHub issues if gh CLI is available
if command -v gh &> /dev/null; then
  echo "## Recent GitHub Issues"
  echo ""

  # Get assigned issues
  gh issue list --assignee @me --limit 5 --json number,title,state | \
    jq -r '.[] | "  - #\(.number): \(.title) [\(.state)]"'
  echo ""
fi

# Load Linear issues if linear CLI is available
if command -v linear &> /dev/null; then
  echo "## Recent Linear Issues"
  echo ""

  # Get assigned issues
  linear issue list --assignee @me --limit 5 2>/dev/null | head -n 10
  echo ""
fi

# Check for CHANGELOG or ROADMAP
if [ -f "CHANGELOG.md" ]; then
  echo "## Recent Changelog"
  echo ""
  head -n 15 CHANGELOG.md
  echo ""
fi

exit 0
chmod +x .factory/hooks/load-issues.sh
​
Check and install dependencies
Automatically ensure dependencies are up-to-date.
Create .factory/hooks/check-dependencies.sh:
#!/bin/bash
set -e

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "📦 Checking dependencies..."
echo ""

# Node.js projects
if [ -f "package.json" ]; then
  if [ ! -d "node_modules" ]; then
    echo "⚠️ node_modules not found"
    echo "Suggestion: Run 'npm install' or 'yarn install'"
    echo ""
  else
    # Check if package.json is newer than node_modules
    if [ "package.json" -nt "node_modules" ]; then
      echo "⚠️ package.json modified since last install"
      echo "Suggestion: Run 'npm install' to update dependencies"
      echo ""
    else
      echo "✓ Node dependencies up to date"
      echo ""
    fi
  fi
fi

# Python projects
if [ -f "requirements.txt" ]; then
  if [ ! -d "venv" ]; then
    echo "⚠️ Python virtual environment not found"
    echo "Suggestion: Run 'python -m venv venv && source venv/bin/activate && pip install -r requirements.txt'"
    echo ""
  else
    echo "✓ Python virtual environment exists"
    echo ""
  fi
fi

# Go projects
if [ -f "go.mod" ]; then
  if [ ! -d "vendor" ] && ! command -v go &> /dev/null; then
    echo "⚠️ Go not found in PATH"
    echo "Suggestion: Install Go from https://go.dev"
    echo ""
  else
    echo "✓ Go environment ready"
    echo ""
  fi
fi

# Ruby projects
if [ -f "Gemfile" ]; then
  if ! command -v bundle &> /dev/null; then
    echo "⚠️ Bundler not found"
    echo "Suggestion: gem install bundler"
    echo ""
  else
    if ! bundle check &>/dev/null; then
      echo "⚠️ Ruby gems out of date"
      echo "Suggestion: bundle install"
      echo ""
    else
      echo "✓ Ruby gems up to date"
      echo ""
    fi
  fi
fi

exit 0
chmod +x .factory/hooks/check-dependencies.sh
​
Load custom project guidelines
Provide project-specific instructions automatically.
Create .factory/AGENTS.md with project guidelines:
# Project Guidelines for Droid

## Code Style
- Use TypeScript for all new files
- Follow ESLint configuration strictly
- Prefer functional components in React
- Use async/await over promises

## Testing
- Write tests for all new features
- Run `npm test` before committing
- Maintain >80% code coverage

## Architecture
- Keep components under 200 lines
- Use Redux for global state
- Local state for component-specific data
- No direct API calls from components (use services)

## Git Workflow
- Create feature branches from `dev`
- Name branches: `feature/FAC-123-description`
- Write descriptive commit messages
- Squash commits before merging
Create .factory/hooks/load-guidelines.sh:
#!/bin/bash
set -e

input=$(cat)
source_type=$(echo "$input" | jq -r '.source')

if [ "$source_type" != "startup" ]; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')

# Load project-specific guidelines
if [ -f "$cwd/.factory/AGENTS.md" ]; then
  echo "## Project Guidelines"
  echo ""
  cat "$cwd/.factory/AGENTS.md"
  echo ""
fi

# Load PR templates
if [ -f "$cwd/.github/PULL_REQUEST_TEMPLATE.md" ]; then
  echo "## PR Template Reference"
  echo ""
  head -n 20 "$cwd/.github/PULL_REQUEST_TEMPLATE.md"
  echo ""
fi

exit 0
chmod +x .factory/hooks/load-guidelines.sh
​
Smart context based on Git branch
Load different context based on the current branch:
Create .factory/hooks/branch-context.sh:
#!/bin/bash
set -e

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

if [ ! -d ".git" ]; then
  exit 0
fi

branch=$(git branch --show-current)

echo "## Current Context: $branch"
echo ""

case "$branch" in
  main|master)
    echo "⚠️ Working on production branch!"
    echo "Extra care needed - changes go to production"
    echo ""

    # Show recent production issues
    if command -v gh &> /dev/null; then
      echo "Recent production issues:"
      gh issue list --label production --limit 3 --json number,title | \
        jq -r '.[] | "  - #\(.number): \(.title)"'
      echo ""
    fi
    ;;

  dev|develop)
    echo "📦 Working on development branch"
    echo "Standard development workflow applies"
    echo ""
    ;;

  feature/*)
    feature_name="${branch#feature/}"
    echo "🔨 Feature branch: $feature_name"
    echo ""

    # Try to find related issue
    if [[ $feature_name =~ FAC-[0-9]+ ]]; then
      issue_id="${BASH_REMATCH[0]}"
      echo "Related Linear issue: $issue_id"

      # Fetch issue details if linear CLI available
      if command -v linear &> /dev/null; then
        linear issue view "$issue_id" 2>/dev/null || true
        echo ""
      fi
    fi

    # Show uncommitted changes
    if [ -n "$(git status --short)" ]; then
      echo "Uncommitted changes:"
      git status --short | head -n 10
      echo ""
    fi
    ;;

  hotfix/*)
    echo "🚨 HOTFIX BRANCH"
    echo "Critical bug fix - expedite review and deployment"
    echo ""
    ;;
esac

exit 0
chmod +x .factory/hooks/branch-context.sh
​
Real-world examples
​
Example 1: Monorepo workspace setup
Automatically switch to the right package:
Create .factory/hooks/monorepo-setup.sh:
#!/bin/bash
set -e

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')

# Check if this is a monorepo
if [ ! -f "$cwd/package.json" ] || ! grep -q '"workspaces"' "$cwd/package.json"; then
  exit 0
fi

echo "## Monorepo Structure"
echo ""

# List workspaces
if command -v npm &> /dev/null; then
  echo "Available workspaces:"
  npm ls --workspaces --depth=0 2>/dev/null | grep -E "^[├└]" | sed 's/^[├└]── /  - /'
  echo ""
fi

# Show recent changes by workspace
if [ -d ".git" ]; then
  echo "Recently modified workspaces:"
  git diff --name-only HEAD~5..HEAD | \
    grep -E "^(packages|apps)/" | \
    cut -d/ -f1-2 | \
    sort -u | \
    head -n 5 | \
    sed 's/^/  - /'
  echo ""
fi

exit 0
​
Example 2: Docker environment check
Ensure Docker services are running:
Create .factory/hooks/check-docker.sh:
#!/bin/bash

if ! command -v docker &> /dev/null; then
  exit 0
fi

# Check if Docker daemon is running
if ! docker info &>/dev/null; then
  echo "⚠️ Docker daemon not running"
  echo "Suggestion: Start Docker Desktop or run 'sudo systemctl start docker'"
  echo ""
  exit 0
fi

echo "## Docker Environment"
echo ""

# Check for docker-compose.yml
if [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ]; then
  echo "Docker Compose configuration found"

  # Check if services are running
  if docker-compose ps &>/dev/null; then
    echo ""
    echo "Running services:"
    docker-compose ps --format "table {{.Name}}\t{{.Status}}" | tail -n +2 | sed 's/^/  /'
  else
    echo "Suggestion: Start services with 'docker-compose up -d'"
  fi
  echo ""
fi

exit 0
​
Best practices
1
Keep context concise

Only load essential information:
# Show summary, not full content
echo "Found $(wc -l < README.md) lines in README"
# Instead of: cat README.md
2
Cache expensive operations

Avoid repeated expensive checks:
CACHE_FILE="/tmp/droid-context-$(date +%Y%m%d)"
if [ -f "$CACHE_FILE" ]; then
  cat "$CACHE_FILE"
  exit 0
fi

# Generate context...
echo "$context" | tee "$CACHE_FILE"
3
Use DROID_ENV_FILE for environment

Persist environment variables correctly:
if [ -n "$DROID_ENV_FILE" ]; then
  echo 'export NODE_ENV=development' >> "$DROID_ENV_FILE"
  echo 'export API_URL=http://localhost:3000' >> "$DROID_ENV_FILE"
fi
4
Handle missing tools gracefully

Check before using external commands:
if command -v gh &> /dev/null; then
  gh issue list
else
  echo "GitHub CLI not installed (skip with: brew install gh)"
fi
5
Provide actionable suggestions

Tell users what to do next:
echo "⚠️ Dependencies out of date"
echo "Action: Run 'npm install' to update"
echo "Or: Let me handle this - just ask 'install dependencies'"
​
Troubleshooting
Problem: Too much information loaded
Solution: Summarize and link to details:
echo "README.md exists ($(wc -l < README.md) lines)"
echo "Run 'cat README.md' to view full content"
Problem: Variables not available in Bash commands
Solution: Verify DROID_ENV_FILE usage:
if [ -z "$DROID_ENV_FILE" ]; then
  echo "DROID_ENV_FILE not available" >&2
  exit 1
fi

# Append, don't overwrite
echo 'export VAR=value' >> "$DROID_ENV_FILE"
Problem: Session start takes too long
Solution: Run expensive operations asynchronously:
# Start background job for slow operations
(
  sleep 1  # Let Droid start first
  expensive_operation > /tmp/droid-context.txt
) &

# Return immediately with basic context
echo "Loading detailed context in background..."
​

Testing Automation

Copy page

Automate test execution, coverage tracking, and test result validation with hooks

This cookbook shows how to automatically run tests when Droid modifies code, maintain test coverage, and enforce testing requirements.
​
How it works
Testing hooks can:
Auto-run tests: Execute tests after code changes
Track coverage: Monitor and enforce coverage thresholds
Validate test files: Ensure tests exist for new code
Run specific tests: Execute only relevant test suites
Generate reports: Create test and coverage reports
​
Prerequisites
Install testing frameworks for your stack:

JavaScript/TypeScript

Python

Go
npm install -D jest @testing-library/react vitest
npm install -D @vitest/coverage-v8  # For coverage
​
Basic testing automation
​
Run tests after code changes
Automatically run tests when Droid edits files.
Create .factory/hooks/run-tests.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only run tests after file write/edit
if [ "$tool_name" != "Write" ] && [ "$tool_name" != "Edit" ]; then
  exit 0
fi

# Skip non-code files
if ! echo "$file_path" | grep -qE '\.(ts|tsx|js|jsx|py|go)$'; then
  exit 0
fi

# Skip test files themselves
if echo "$file_path" | grep -qE '\.(test|spec)\.(ts|tsx|js|jsx)$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "🧪 Running tests for changed file..."

# Determine test command based on file type
case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    # Find corresponding test file
    test_file=$(echo "$file_path" | sed -E 's/\.(ts|tsx|js|jsx)$/.test.\1/')

    if [ ! -f "$test_file" ]; then
      # Try alternate naming
      test_file=$(echo "$file_path" | sed -E 's/\.(ts|tsx|js|jsx)$/.spec.\1/')
    fi

    if [ -f "$test_file" ]; then
      # Run specific test file
      if command -v npm &> /dev/null && grep -q '"test"' package.json; then
        npm test -- "$test_file" 2>&1 || {
          echo "❌ Tests failed for $test_file" >&2
          echo "Please fix the failing tests." >&2
          exit 2
        }
        echo "✓ Tests passed for $test_file"
      fi
    else
      echo "⚠️ No test file found for $file_path"
      echo "Consider creating: $test_file"
    fi
    ;;

  *.py)
    # Run pytest for Python files
    if command -v pytest &> /dev/null; then
      # Find test file
      test_file=$(echo "$file_path" | sed 's/\.py$//' | sed 's|^src/|tests/test_|')_test.py

      if [ -f "$test_file" ]; then
        pytest "$test_file" -v 2>&1 || {
          echo "❌ Tests failed" >&2
          exit 2
        }
        echo "✓ Tests passed"
      else
        echo "⚠️ No test file found at $test_file"
      fi
    fi
    ;;

  *.go)
    # Run go test
    if command -v go &> /dev/null; then
      package=$(dirname "$file_path")
      go test "./$package" -v 2>&1 || {
        echo "❌ Tests failed" >&2
        exit 2
      }
      echo "✓ Tests passed"
    fi
    ;;
esac

exit 0
chmod +x .factory/hooks/run-tests.sh
Add to .factory/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$DROID_PROJECT_DIR\"/.factory/hooks/run-tests.sh",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
​
Enforce test coverage
Block changes that decrease test coverage.
Create .factory/hooks/check-coverage.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only check code files
if ! echo "$file_path" | grep -qE '\.(ts|tsx|js|jsx|py)$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Minimum coverage threshold
MIN_COVERAGE="${DROID_MIN_COVERAGE:-80}"

echo "📊 Checking test coverage..."

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    # Jest coverage
    if command -v npm &> /dev/null && grep -q '"test"' package.json; then
      # Run coverage for specific file
      coverage_output=$(npm test -- --coverage --collectCoverageFrom="$file_path" --silent 2>&1 || true)

      # Extract coverage percentage
      if echo "$coverage_output" | grep -qE "All files.*[0-9]+(\.[0-9]+)?%"; then
        coverage=$(echo "$coverage_output" | grep "All files" | grep -oE "[0-9]+(\.[0-9]+)?%" | head -1 | tr -d '%')

        if (( $(echo "$coverage < $MIN_COVERAGE" | bc -l) )); then
          echo "❌ Coverage too low: ${coverage}% (minimum: ${MIN_COVERAGE}%)" >&2
          echo "Please add tests to improve coverage." >&2
          exit 2
        fi

        echo "✓ Coverage: ${coverage}%"
      fi
    fi
    ;;

  *.py)
    # Python coverage
    if command -v pytest &> /dev/null; then
      coverage_output=$(pytest --cov="$file_path" --cov-report=term 2>&1 || true)

      if echo "$coverage_output" | grep -qE "TOTAL.*[0-9]+%"; then
        coverage=$(echo "$coverage_output" | grep "TOTAL" | grep -oE "[0-9]+%" | tr -d '%')

        if [ "$coverage" -lt "$MIN_COVERAGE" ]; then
          echo "❌ Coverage too low: ${coverage}% (minimum: ${MIN_COVERAGE}%)" >&2
          exit 2
        fi

        echo "✓ Coverage: ${coverage}%"
      fi
    fi
    ;;
esac

exit 0
chmod +x .factory/hooks/check-coverage.sh
Configure coverage threshold:
# Add to ~/.bashrc or ~/.zshrc
export DROID_MIN_COVERAGE=75
​
Require tests for new files
Ensure new code files have corresponding tests.
Create .factory/hooks/require-tests.sh:
#!/bin/bash

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only check Write operations (new files)
if [ "$tool_name" != "Write" ]; then
  exit 0
fi

# Only check code files in src/
if ! echo "$file_path" | grep -qE '^src/.*\.(ts|tsx|js|jsx|py)$'; then
  exit 0
fi

# Skip if it's already a test file
if echo "$file_path" | grep -qE '\.(test|spec)\.(ts|tsx|js|jsx)$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')

# Determine expected test file location
case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    test_file1=$(echo "$file_path" | sed -E 's/\.(ts|tsx|js|jsx)$/.test.\1/')
    test_file2=$(echo "$file_path" | sed -E 's/\.(ts|tsx|js|jsx)$/.spec.\1/')
    test_file3=$(echo "$file_path" | sed 's|^src/|tests/|; s/\.(ts|tsx|js|jsx)$/.test.\1/')
    ;;

  *.py)
    test_file1=$(echo "$file_path" | sed 's|^src/|tests/|; s/\.py$/_test.py/')
    test_file2=$(echo "$file_path" | sed 's|^src/|tests/test_|')
    test_file3=""
    ;;
esac

# Check if any test file exists
found_test=false
for test_file in "$test_file1" "$test_file2" "$test_file3"; do
  if [ -n "$test_file" ] && [ -f "$cwd/$test_file" ]; then
    found_test=true
    break
  fi
done

if [ "$found_test" = false ]; then
  echo "⚠️ No test file found for $file_path" >&2
  echo "" >&2
  echo "Please create a test file at one of:" >&2
  echo "  - $test_file1" >&2
  [ -n "$test_file2" ] && echo "  - $test_file2" >&2
  [ -n "$test_file3" ] && echo "  - $test_file3" >&2
  echo "" >&2
  echo "Or ask me: 'Create tests for $file_path'" >&2

  # Warning only, don't block
  # Change to exit 2 to enforce test creation
fi

exit 0
chmod +x .factory/hooks/require-tests.sh
​
Advanced testing automation
​
Smart test selection
Only run tests affected by changes.
Create .factory/hooks/run-affected-tests.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

if [ "$tool_name" != "Write" ] && [ "$tool_name" != "Edit" ]; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

# Find tests that import this file
echo "🔍 Finding affected tests..."

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    # Find test files that import this file
    filename=$(basename "$file_path" | sed -E 's/\.(ts|tsx|js|jsx)$//')
    module_name=$(echo "$file_path" | sed 's|^src/||; s/\.(ts|tsx|js|jsx)$//')

    # Search for imports
    affected_tests=$(grep -rl "from.*['\"].*$module_name['\"]" . \
      --include="*.test.ts" \
      --include="*.test.tsx" \
      --include="*.test.js" \
      --include="*.test.jsx" \
      --include="*.spec.ts" \
      --include="*.spec.tsx" \
      2>/dev/null || true)

    if [ -n "$affected_tests" ]; then
      echo "Running affected tests:"
      echo "$affected_tests" | sed 's/^/  - /'
      echo ""

      # Run tests
      echo "$affected_tests" | while read -r test_file; do
        npm test -- "$test_file" 2>&1 || {
          echo "❌ Test failed: $test_file" >&2
          exit 2
        }
      done

      echo "✓ All affected tests passed"
    else
      echo "No affected tests found"
    fi
    ;;
esac

exit 0
chmod +x .factory/hooks/run-affected-tests.sh
​
Snapshot testing validation
Detect and validate snapshot updates.
Create .factory/hooks/validate-snapshots.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Check if snapshot files changed
if ! echo "$file_path" | grep -qE '__snapshots__/.*\.snap$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "📸 Snapshot file modified: $file_path"
echo ""

# Run tests in update mode to verify
test_file=$(echo "$file_path" | sed 's|/__snapshots__/.*\.snap$|.test.ts|')

if [ ! -f "$test_file" ]; then
  test_file=$(echo "$file_path" | sed 's|/__snapshots__/.*\.snap$|.spec.ts|')
fi

if [ -f "$test_file" ]; then
  echo "Verifying snapshot update..."

  if npm test -- "$test_file" -u 2>&1; then
    echo "✓ Snapshot update verified"
    echo ""
    echo "⚠️ Remember to review snapshot changes before committing:"
    echo "  git diff $file_path"
  else
    echo "❌ Snapshot verification failed" >&2
    exit 2
  fi
else
  echo "⚠️ Could not find test file for snapshot"
fi

exit 0
chmod +x .factory/hooks/validate-snapshots.sh
​
Test performance monitoring
Track test execution time and warn on slow tests.
Create .factory/hooks/monitor-test-perf.py:
#!/usr/bin/env python3
"""
Monitor test execution time and report slow tests.
"""
import json
import sys
import subprocess
import time
import re

# Slow test threshold in seconds
SLOW_TEST_THRESHOLD = 5.0

def run_tests_with_timing(test_file):
    """Run tests and capture timing information."""
    start_time = time.time()

    try:
        result = subprocess.run(
            ['npm', 'test', '--', test_file, '--verbose'],
            capture_output=True,
            text=True,
            timeout=60
        )

        elapsed = time.time() - start_time

        # Parse test output for individual test times
        slow_tests = []
        for line in result.stdout.split('\n'):
            # Look for test timing info
            match = re.search(r'(.*?)\s+\((\d+)ms\)', line)
            if match:
                test_name = match.group(1).strip()
                test_time_ms = int(match.group(2))
                test_time_s = test_time_ms / 1000.0

                if test_time_s > SLOW_TEST_THRESHOLD:
                    slow_tests.append((test_name, test_time_s))

        return elapsed, slow_tests, result.returncode

    except subprocess.TimeoutExpired:
        return None, [], 1

try:
    input_data = json.load(sys.stdin)
    file_path = input_data.get('tool_input', {}).get('file_path', '')

    if not file_path or not file_path.endswith(('.test.ts', '.test.tsx', '.spec.ts', '.spec.tsx')):
        sys.exit(0)

    print(f"⏱️  Monitoring test performance for {file_path}...")

    elapsed, slow_tests, returncode = run_tests_with_timing(file_path)

    if elapsed is not None:
        print(f"\nTotal test time: {elapsed:.2f}s")

        if slow_tests:
            print(f"\n⚠️  Found {len(slow_tests)} slow test(s):")
            for test_name, test_time in slow_tests:
                print(f"  - {test_name}: {test_time:.2f}s")
            print("\nConsider optimizing these tests or mocking expensive operations.")
        else:
            print("✓ All tests running within acceptable time")

        # Don't block on slow tests, just warn
        sys.exit(returncode)
    else:
        print("❌ Tests timed out", file=sys.stderr)
        sys.exit(2)

except Exception as e:
    print(f"Error monitoring tests: {e}", file=sys.stderr)
    sys.exit(0)
chmod +x .factory/hooks/monitor-test-perf.py
​
Test flakiness detector
Detect and report flaky tests:
Create .factory/hooks/detect-flaky-tests.sh:
#!/bin/bash
set -e

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only check test files
if ! echo "$file_path" | grep -qE '\.(test|spec)\.(ts|tsx|js|jsx)$'; then
  exit 0
fi

cwd=$(echo "$input" | jq -r '.cwd')
cd "$cwd"

echo "🎲 Checking for test flakiness..."

# Run tests multiple times
RUNS=3
failures=0

for i in $(seq 1 $RUNS); do
  echo "Run $i/$RUNS..."

  if ! npm test -- "$file_path" --silent 2>&1; then
    ((failures++))
  fi
done

if [ $failures -gt 0 ] && [ $failures -lt $RUNS ]; then
  echo "" >&2
  echo "⚠️ FLAKY TEST DETECTED" >&2
  echo "Test passed $((RUNS - failures))/$RUNS times" >&2
  echo "" >&2
  echo "This test is unreliable and should be fixed." >&2
  echo "Common causes:" >&2
  echo "  - Race conditions" >&2
  echo "  - Timing dependencies" >&2
  echo "  - Non-deterministic data" >&2
  echo "  - External dependencies" >&2

  # Warning only, don't block
  exit 0
elif [ $failures -eq $RUNS ]; then
  echo "❌ Test consistently fails" >&2
  exit 2
else
  echo "✓ Test is stable ($RUNS/$RUNS passed)"
fi

exit 0
chmod +x .factory/hooks/detect-flaky-tests.sh
​
Best practices
1
Run tests asynchronously when possible

Don’t block Droid unnecessarily:
# Run tests in background, report later
(npm test "$file" > /tmp/test-results.txt 2>&1 &)
echo "Tests running in background..."
2
Set appropriate timeouts

Allow enough time for test suites:
{
  "timeout": 120  // 2 minutes for test suites
}
3
Use test file conventions

Follow standard naming patterns:
src/components/Button.tsx
src/components/Button.test.tsx  // Co-located

Or:

src/components/Button.tsx
tests/components/Button.test.tsx  // Separate directory
4
Make coverage configurable

Different files may need different thresholds:
# .factory/.coverage-config
src/critical/*.ts:90
src/utils/*.ts:75
src/experimental/*.ts:50
5
Cache test results

Skip tests if code hasn’t changed:
hash=$(md5sum "$file_path")
cache_file="/tmp/test-cache-$hash"

if [ -f "$cache_file" ]; then
  echo "✓ Tests passed (cached)"
  exit 0
fi
​
Troubleshooting
Problem: Test execution blocks workflow
Solution: Run only unit tests, skip integration:
# Fast unit tests only
npm test -- --testPathPattern="unit" "$file"

# Or configure in package.json
{
  "scripts": {
    "test:fast": "jest --testPathIgnorePatterns=integration"
  }
}
Problem: Tests fail in hooks but pass manually
Solution: Check environment differences:
# Ensure same environment
export NODE_ENV=test
export CI=true

# Use project test script
npm test  # Not direct jest call
Problem: Coverage includes generated files
Solution: Configure coverage exclusions:
// jest.config.js
{
  "coveragePathIgnorePatterns": [
    "/node_modules/",
    "/.gen/",
    "/dist/",
    "\\.d\\.ts$"
  ]
}
​
