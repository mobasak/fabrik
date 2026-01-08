# Power User Setup Checklist

> Complete checklist to configure Droid for maximum effectiveness with IDE integration, memory, skills, and automation.

This checklist transforms a basic Droid installation into a fully optimized development environment. Each section builds on the previous one—complete them in order for best results.

<Note>
  Each section can be done independently if you prefer to spread it out.
</Note>

<Info>
  **Using Factory App?** Most of this guide applies to both CLI and [Factory App](/web/getting-started/overview). Where the experience differs, we've noted the App-specific approach.
</Info>

***

## Level 1: Essential Setup

These foundational items give you the biggest immediate impact.

<Steps>
  <Step title="Install the Factory IDE Plugin">
    The IDE plugin provides real-time context—open files, errors, selections—so Droid sees what you see.

    **VSCode/Cursor:**

    1. Open Extensions (`Cmd+Shift+X`)
    2. Search "Factory"
    3. Install and reload

    **Verify:** Run `droid` and check for "IDE connected" in the status bar.
  </Step>

  <Step title="Create your AGENTS.md">
    Create a basic [`AGENTS.md`](/cli/configuration/agents-md) at your repository root:

    ```markdown  theme={null}
    # Project Guidelines

    ## Build & Test
    - Build: `npm run build`
    - Test: `npm test`
    - Lint: `npm run lint`

    ## Code Style
    - Use TypeScript strict mode
    - Prefer functional components in React
    - Write tests for new features
    ```

    Start minimal—you'll expand this as you work. See the [AGENTS.md guide](/cli/configuration/agents-md) for more examples.
  </Step>

  <Step title="Configure your default model">
    Set your preferred model in settings:

    **CLI:**

    ```bash  theme={null}
    droid
    > /settings
    # Navigate to Model and select your default
    ```

    **Factory App:** Use the model selector dropdown in the chat interface.

    **Recommendation:** Start with Claude Opus 4.5 (default) for complex work, switch to Haiku 4.5 or GPT-5.1-Codex for routine tasks.
  </Step>
</Steps>

<Check>
  **Checkpoint:** You should now have IDE integration, basic project context, and your preferred model configured.
</Check>

***

## Level 2: Memory & Context

Build persistent memory so Droid remembers your preferences across sessions.

<Steps>
  <Step title="Create a memories file">
    Create `~/.factory/memories.md` for personal preferences:

    ```markdown  theme={null}
    # My Development Preferences

    ## Code Style
    - I prefer arrow functions over function declarations
    - I like early returns over nested conditionals
    - I use 2-space indentation

    ## Testing
    - I use React Testing Library, not Enzyme
    - I prefer integration tests over unit tests for components
    - Mock external APIs, not internal modules

    ## Past Decisions
    - [2024-01] Chose Zustand over Redux for state management
    - [2024-02] Using Tailwind CSS for styling
    ```

    Update this file whenever you find yourself repeating instructions to Droid.
  </Step>

  <Step title="Reference memories in AGENTS.md">
    Add to your `AGENTS.md`:

    ```markdown  theme={null}
    ## Personal Preferences
    Refer to `~/.factory/memories.md` for my coding preferences and past decisions.
    ```
  </Step>

  <Step title="Create project-specific memories (optional)">
    For team projects, create `.factory/memories.md`:

    ```markdown  theme={null}
    # Project Memories

    ## Architecture Decisions
    - We use the repository pattern for data access
    - All API routes go through the /api/v1 prefix
    - Feature flags are managed via LaunchDarkly

    ## Known Issues
    - The auth service has a 5-second timeout issue (#123)
    - Legacy users table uses snake_case columns
    ```
  </Step>
</Steps>

<Check>
  **Checkpoint:** Droid now has access to your preferences and project history without you repeating them.
</Check>

<Tip>
  **Want automated memory capture?** Set up a hook to automatically save memories when you say "remember this:". See [Memory Management](/guides/power-user/memory-management#automatic-memory-capture) for setup instructions, or explore the [memory-capture skill example](https://github.com/Factory-AI/factory/tree/main/examples/power-user-skills/memory-capture).
</Tip>

***

## Level 3: Rules & Conventions

Organize your coding standards so Droid follows them consistently.

<Steps>
  <Step title="Create a rules directory">
    Create `.factory/rules/` in your project:

    ```
    .factory/
    └── rules/
        ├── typescript.md
        ├── testing.md
        └── security.md
    ```
  </Step>

  <Step title="Add TypeScript rules">
    Create `.factory/rules/typescript.md`:

    ```markdown  theme={null}
    # TypeScript Conventions

    ## General
    - Use `interface` for object types, `type` for unions/intersections
    - Avoid `any` - use `unknown` with type guards instead
    - Export types alongside their implementations

    ## React Components
    - Use functional components with TypeScript FC type
    - Props interfaces should be named `{ComponentName}Props`
    - Use `React.ReactNode` for children, not `React.ReactChild`

    ## Imports
    - Group imports: React, external libs, internal modules, types
    - Use absolute imports from `@/` prefix
    - Avoid barrel files (index.ts re-exports) for performance
    ```
  </Step>

  <Step title="Add testing rules">
    Create `.factory/rules/testing.md`:

    ```markdown  theme={null}
    # Testing Conventions

    ## File Organization
    - Test files live next to source: `Component.tsx` → `Component.test.tsx`
    - Integration tests go in `__tests__/integration/`
    - E2E tests go in `e2e/`

    ## Test Structure
    - Use descriptive test names: "should [action] when [condition]"
    - One assertion per test when possible
    - Use `beforeEach` for common setup, not `beforeAll`

    ## Mocking
    - Mock at the boundary (API calls, not internal functions)
    - Use MSW for API mocking in integration tests
    - Reset mocks in `afterEach`
    ```
  </Step>

  <Step title="Reference rules in AGENTS.md">
    Update your `AGENTS.md`:

    ```markdown  theme={null}
    ## Coding Standards
    Follow the conventions documented in:
    - `.factory/rules/typescript.md` - TypeScript and React patterns
    - `.factory/rules/testing.md` - Testing conventions
    - `.factory/rules/security.md` - Security requirements
    ```
  </Step>
</Steps>

<Check>
  **Checkpoint:** Your coding standards are now documented and Droid will follow them consistently.
</Check>

<Tip>
  **Enforce rules automatically:** Use [PostToolUse hooks](/cli/configuration/hooks-guide) to run linters after edits. See [Code Validation hooks](/guides/hooks/code-validation) for examples.
</Tip>

***

## Level 4: Skills & Automation

Add reusable skills and automation hooks.

<Info>
  **Three ways to automate:**

  * **[Skills](/cli/configuration/skills)** — Droid invokes them based on task context
  * **[Hooks](/cli/configuration/hooks-guide)** — Run automatically on specific events
  * **[Custom Slash Commands](/cli/configuration/custom-slash-commands)** — You invoke with `/command-name`
</Info>

<Steps>
  <Step title="Create a prompt refiner skill">
    Create `~/.factory/skills/prompt-refiner/SKILL.md`:

    ```markdown  theme={null}
    ---
    name: prompt-refiner
    description: Improve prompts before sending them to get better results. Use when you want to refine a task description.
    ---

    # Prompt Refiner

    ## Instructions

    When the user wants to refine a prompt:

    1. Ask for their draft prompt or task description
    2. Analyze it for:
       - Clarity: Is the goal specific and measurable?
       - Context: Does it include relevant background?
       - Constraints: Are requirements and limitations stated?
       - Examples: Would examples help clarify expectations?
    3. Suggest an improved version with explanations
    4. Offer to iterate if needed

    ## Good Prompt Patterns

    - Start with the outcome: "Create a..." not "I want you to..."
    - Include acceptance criteria: "The result should..."
    - Specify format: "Return as JSON/markdown/code"
    - Mention constraints: "Must be compatible with...", "Should not modify..."
    ```
  </Step>

  <Step title="Add an auto-formatting hook">
    Run `/hooks` and add a PostToolUse hook for automatic formatting:

    ```json  theme={null}
    {
      "hooks": {
        "PostToolUse": [
          {
            "matcher": "Edit|Write",
            "hooks": [
              {
                "type": "command",
                "command": "cd \"$FACTORY_PROJECT_DIR\" && npx prettier --write \"$(jq -r '.tool_input.file_path' 2>/dev/null || echo '')\" 2>/dev/null || true"
              }
            ]
          }
        ]
      }
    }
    ```

    This automatically formats files after Droid edits them.
  </Step>

  <Step title="Add a test-on-edit hook (optional)">
    Run related tests after edits:

    ```json  theme={null}
    {
      "hooks": {
        "PostToolUse": [
          {
            "matcher": "Edit",
            "hooks": [
              {
                "type": "command",
                "command": "cd \"$FACTORY_PROJECT_DIR\" && jq -r '.tool_input.file_path' | xargs -I {} npm test -- --findRelatedTests {} --passWithNoTests 2>/dev/null || true"
              }
            ]
          }
        ]
      }
    }
    ```
  </Step>
</Steps>

<Check>
  **Checkpoint:** You now have reusable skills and automatic formatting/testing.
</Check>

***

## Level 5: Token Optimization

Fine-tune for cost efficiency without sacrificing quality.

<Steps>
  <Step title="Enable Spec Mode for complex work">
    Use `Shift+Tab` or `/spec` before starting features that touch multiple files. This prevents expensive false starts.
  </Step>

  <Step title="Configure model switching">
    Set up a spec mode model for planning:

    ```bash  theme={null}
    droid
    > /settings
    # Set Spec Mode Model to a reasoning-heavy model
    ```

    Use Opus 4.5 for planning, then Sonnet or Codex for implementation.
  </Step>

  <Step title="Run the readiness report">
    Check your project's AI-readiness:

    **CLI:**

    ```bash  theme={null}
    droid
    > /readiness-report
    ```

    **Factory App:** View your readiness score in the [Agent Readiness Dashboard](/web/agent-readiness/dashboard).

    Address high-impact items first—linting, type checking, and fast tests dramatically reduce token waste.
  </Step>
</Steps>

***

## Quick Reference: File Locations

| Purpose                | Personal                            | Project                           |
| ---------------------- | ----------------------------------- | --------------------------------- |
| **Skills**             | `~/.factory/skills/<name>/SKILL.md` | `.factory/skills/<name>/SKILL.md` |
| **Memory**             | `~/.factory/memories.md`            | `.factory/memories.md`            |
| **Rules**              | `~/.factory/rules/*.md`             | `.factory/rules/*.md`             |
| **Settings**           | `~/.factory/settings.json`          | `.factory/settings.json`          |
| **Hooks**              | In settings.json                    | In settings.json                  |
| **Agent instructions** | `~/.factory/AGENTS.md`              | `./AGENTS.md`                     |
| **Custom droids**      | `~/.factory/droids/<name>.md`       | `.factory/droids/<name>.md`       |

***

## Verification Checklist

Run through this checklist to verify your setup:

* [ ] IDE plugin shows "connected" when running Droid
* [ ] `AGENTS.md` exists with build/test commands
* [ ] Memories file created with your preferences
* [ ] Rules directory with at least one rules file
* [ ] At least one custom skill created
* [ ] Auto-formatting hook configured
* [ ] Readiness report shows Level 2 or higher

***

## Next Steps

<CardGroup cols={2}>
  <Card title="Prompt Crafting" href="/guides/power-user/prompt-crafting" icon="wand-magic-sparkles">
    Learn model-specific prompting techniques
  </Card>

  <Card title="Token Efficiency" href="/guides/power-user/token-efficiency" icon="gauge-high">
    Strategies for reducing token usage
  </Card>

  <Card title="Memory Management" href="/guides/power-user/memory-management" icon="brain">
    Advanced memory and context patterns
  </Card>

  <Card title="Rules Guide" href="/guides/power-user/rules-conventions" icon="scale-balanced">
    Organizing team conventions effectively
  </Card>
</CardGroup>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Memory and Context Management

> Build persistent memory so Droid remembers your preferences, decisions, and project history across sessions.

Droid doesn't have built-in memory between sessions, but you can create a powerful memory system using markdown files, AGENTS.md references, and hooks. This guide shows you how to build memory that persists and grows.

<Info>
  **Works with Factory App:** These memory patterns work identically in both CLI and [Factory App](/web/getting-started/overview)—just ensure your working directory is set to your repository root.
</Info>

***

## The Memory System Architecture

Your memory system consists of three layers:

```
┌─────────────────────────────────────────────────────┐
│                    AGENTS.md                         │
│         (References and orchestrates memory)         │
└─────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│ Personal Memory │ │ Project     │ │ Rules &         │
│ ~/.factory/     │ │ Memory      │ │ Conventions     │
│ memories.md     │ │ .factory/   │ │ .factory/rules/ │
│                 │ │ memories.md │ │                 │
│ • Preferences   │ │ • Decisions │ │ • Standards     │
│ • Style         │ │ • History   │ │ • Patterns      │
│ • Tools         │ │ • Context   │ │ • Guidelines    │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

***

## Setting Up Personal Memory

Personal memory follows you across all projects.

### Step 1: Create the Memory File

Create `~/.factory/memories.md`:

```markdown  theme={null}
# My Development Memory

## Code Style Preferences

### General
- I prefer functional programming patterns over OOP
- I like early returns to reduce nesting
- I use 2-space indentation (but defer to project config)

### TypeScript
- I prefer `interface` over `type` for object shapes
- I use strict mode always
- I avoid `enum` in favor of `as const` objects

### React
- Functional components only
- I prefer Zustand over Redux for state
- I use React Query for server state

## Tool Preferences
- Package manager: pnpm (prefer) > npm > yarn
- Testing: Vitest > Jest
- Formatting: Prettier with defaults
- Linting: ESLint with strict TypeScript rules

## Communication Style
- I prefer concise explanations over verbose ones
- Show me the code first, explain after if needed
- When debugging, show me your reasoning

## Past Decisions (Personal Projects)
- [2024-01] Switched from Create React App to Vite
- [2024-02] Adopted Tailwind CSS as default styling
- [2024-03] Using Supabase for personal projects
```

### Step 2: Reference in AGENTS.md

Add to your `~/.factory/AGENTS.md` or project `AGENTS.md`:

```markdown  theme={null}
## Personal Preferences
My coding preferences and tool choices are documented in `~/.factory/memories.md`.
Refer to this file when making decisions about code style, architecture, or tooling.
```

***

## Setting Up Project Memory

Project memory captures decisions and context specific to a codebase.

### Step 1: Create Project Memory

Create `.factory/memories.md` in your project root:

```markdown  theme={null}
# Project Memory

## Project Context
- **Name**: Acme Dashboard
- **Type**: B2B SaaS application
- **Stack**: Next.js 14, TypeScript, Prisma, PostgreSQL
- **Started**: January 2024

## Architecture Decisions

### 2024-01-15: Database Choice
**Decision**: PostgreSQL over MongoDB
**Reasoning**: Strong relational data model, ACID compliance needed for financial data
**Trade-offs**: More rigid schema, but better for reporting queries

### 2024-02-01: Authentication Approach
**Decision**: NextAuth.js with custom credentials provider
**Reasoning**: Need to integrate with existing enterprise LDAP
**Implementation**: See `src/lib/auth/` for setup

### 2024-02-20: State Management
**Decision**: Zustand for client state, React Query for server state
**Reasoning**: Simpler than Redux, better separation of concerns
**Pattern**: Store files in `src/stores/`, queries in `src/queries/`

## Known Technical Debt
- [ ] Auth refresh token logic needs refactoring (#234)
- [ ] Dashboard queries should be optimized with proper indexes
- [ ] Legacy API endpoints in `/api/v1/` need deprecation

## Domain Knowledge

### Business Rules
- Users belong to Organizations (multi-tenant)
- Subscription tiers: Free, Pro, Enterprise
- Free tier limited to 3 team members
- Data retention: 90 days for Free, unlimited for paid

### Key Entities
- `User`: Individual accounts, can belong to multiple orgs
- `Organization`: Tenant container, has subscription
- `Project`: Work container within an org
- `Task`: Work items within projects

## Team Conventions
- PR titles follow conventional commits
- All PRs need at least one approval
- Deploy to staging on merge to `develop`
- Deploy to production on merge to `main`
```

### Step 2: Reference in Project AGENTS.md

Update your project's `AGENTS.md`:

```markdown  theme={null}
## Project Memory
Architecture decisions, domain knowledge, and project history are documented in `.factory/memories.md`.
Always check this file before making significant architectural or design decisions.
```

***

## Memory Categories

Organize your memories into useful categories:

### Preferences (Personal)

What you like and how you work:

```markdown  theme={null}
## Preferences
- Code style choices
- Tool preferences
- Communication style
- Learning style
```

### Decisions (Project)

What was decided and why:

```markdown  theme={null}
## Decisions
- Architecture choices with reasoning
- Library selections with trade-offs
- Design patterns adopted
- Standards agreed upon
```

### Context (Project)

Background information:

```markdown  theme={null}
## Context
- Business domain knowledge
- Key entities and relationships
- External integrations
- Performance requirements
```

### History (Both)

What happened when:

```markdown  theme={null}
## History
- Major refactors completed
- Migrations performed
- Issues resolved
- Lessons learned
```

***

## Automatic Memory Capture

Create a hook that helps you capture memories as you work.

### The "Remember This" Hook

When you say "remember this:" followed by content, automatically append to memories.

You can trigger memory capture with either **special characters** or **phrases**. Choose based on your preference:

<Tabs>
  <Tab title="# prefix trigger">
    Trigger with `#` at the start of your message for quick capture.

    **Usage:**

    * "#we use the repository pattern"
    * "##I prefer early returns" (double `##` for personal)

    Create `~/.factory/hooks/memory-capture.py`:

    ```python  theme={null}
    #!/usr/bin/env python3
    """Captures messages starting with # and appends to memories.md"""
    import json, sys, os
    from datetime import datetime

    def main():
        try:
            data = json.load(sys.stdin)
            prompt = data.get('prompt', '').strip()

            if not prompt.startswith('#'):
                return

            # ## = personal, # = project
            if prompt.startswith('##'):
                content = prompt[2:].strip()
                mem_file = os.path.expanduser('~/.factory/memories.md')
            else:
                content = prompt[1:].strip()
                project_dir = os.environ.get('FACTORY_PROJECT_DIR', os.getcwd())
                project_factory = os.path.join(project_dir, '.factory')
                if os.path.exists(project_factory):
                    mem_file = os.path.join(project_factory, 'memories.md')
                else:
                    mem_file = os.path.expanduser('~/.factory/memories.md')

            if content:
                timestamp = datetime.now().strftime('%Y-%m-%d')
                with open(mem_file, 'a') as f:
                    f.write(f"\n- [{timestamp}] {content}\n")

                print(json.dumps({'systemMessage': f'✓ Saved to {mem_file}'}))
        except:
            pass

    if __name__ == '__main__':
        main()
    ```
  </Tab>

  <Tab title="Phrase trigger">
    Trigger with phrases like "remember this:", "note:", etc.

    **Usage:**

    * "Remember this: we use the repository pattern"
    * "Note: auth tokens expire after 24 hours"

    Create `~/.factory/hooks/memory-capture.py`:

    ```python  theme={null}
    #!/usr/bin/env python3
    """Captures 'remember this:' statements and appends to memories.md"""
    import json, sys, os
    from datetime import datetime

    def main():
        try:
            data = json.load(sys.stdin)
            prompt = data.get('prompt', '')

            triggers = ['remember this:', 'remember:', 'note:', 'save this:']

            for trigger in triggers:
                if trigger in prompt.lower():
                    idx = prompt.lower().index(trigger)
                    content = prompt[idx + len(trigger):].strip()

                    if content:
                        # Personal if specified, otherwise project
                        if 'personal' in prompt.lower():
                            mem_file = os.path.expanduser('~/.factory/memories.md')
                        else:
                            project_dir = os.environ.get('FACTORY_PROJECT_DIR', os.getcwd())
                            project_factory = os.path.join(project_dir, '.factory')
                            if os.path.exists(project_factory):
                                mem_file = os.path.join(project_factory, 'memories.md')
                            else:
                                mem_file = os.path.expanduser('~/.factory/memories.md')

                        timestamp = datetime.now().strftime('%Y-%m-%d')
                        with open(mem_file, 'a') as f:
                            f.write(f"\n- [{timestamp}] {content}\n")

                        print(json.dumps({'systemMessage': f'✓ Saved to {mem_file}'}))
                    break
        except:
            pass

    if __name__ == '__main__':
        main()
    ```
  </Tab>
</Tabs>

Make it executable and configure the hook:

```bash  theme={null}
chmod +x ~/.factory/hooks/memory-capture.py
```

Add to your hooks configuration via `/hooks`:

```json  theme={null}
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.factory/hooks/memory-capture.py"
          }
        ]
      }
    ]
  }
}
```

**With # prefix:**

* "#we decided to use Zustand for state management"
* "##I prefer early returns" (double `##` saves to personal)

**With phrase triggers:**

* "Remember this: we decided to use Zustand for state management"
* "Note: the auth module uses JWT with 24-hour expiration"

### Alternative: Memory Capture Skill

Instead of a hook, you can use a [skill](/cli/configuration/skills) that Droid invokes when you ask to remember something. This gives you more interactive control over categorization.

See the [memory-capture skill example](https://github.com/Factory-AI/factory/tree/main/examples/power-user-skills/memory-capture) for a ready-to-use implementation.

### Alternative: Custom Slash Command

For quick manual capture, create a [custom slash command](/cli/configuration/custom-slash-commands):

Create `~/.factory/commands/remember.md`:

```markdown  theme={null}
---
description: Save a memory to your memories file
argument-hint: <what to remember>
---

Add this to my memories file (~/.factory/memories.md):

$ARGUMENTS

Format it appropriately based on whether it's a preference, decision, or learning. Include today's date.
```

Then use `/remember we chose PostgreSQL for better ACID compliance` to capture memories on demand.

<Info>
  **Which approach to choose?**

  * **Hook** — Best for automatic capture without extra steps
  * **Skill** — Best when you want Droid to help categorize and format
  * **Slash Command** — Best for quick manual capture with consistent formatting
</Info>

***

## Memory Maintenance

Keep your memories useful with regular maintenance.

### Monthly Review Checklist

```markdown  theme={null}
## Monthly Memory Review

### Personal Memory (~/.factory/memories.md)
- [ ] Remove outdated preferences (tools you no longer use)
- [ ] Update decisions that have changed
- [ ] Add new patterns you've adopted
- [ ] Archive old entries that are no longer relevant

### Project Memory (.factory/memories.md)
- [ ] Review architecture decisions - still valid?
- [ ] Update technical debt items
- [ ] Add new domain knowledge learned
- [ ] Document recent major changes
```

### Archiving Old Memories

When memories become stale, move them to an archive:

```markdown  theme={null}
# memories.md

## Current Decisions
[active decisions here]

## Archive (2023)
<details>
<summary>Archived decisions from 2023</summary>

### 2023-06: Original Auth System
**Decision**: Custom JWT implementation
**Status**: Replaced by NextAuth.js in 2024-02
**Reason for change**: Maintenance burden, security updates

</details>
```

***

## Advanced: Memory-Aware Skills

Create skills that leverage your memory files:

```markdown  theme={null}
---
name: context-aware-implementation
description: Implement features using project memory and conventions.
---

# Context-Aware Implementation

Before implementing any feature:

1. **Check project memory** (`.factory/memories.md`):
   - What architecture decisions apply?
   - What patterns should I follow?
   - What constraints exist?

2. **Check personal preferences** (`~/.factory/memories.md`):
   - What code style does the user prefer?
   - What tools should I use?

3. **Check rules** (`.factory/rules/`):
   - What conventions apply to this file type?
   - What testing requirements exist?

Then implement following all discovered context.
```

***

## Quick Reference

### File Locations

| Memory Type          | Location                 | Scope        |
| -------------------- | ------------------------ | ------------ |
| Personal preferences | `~/.factory/memories.md` | All projects |
| Project decisions    | `.factory/memories.md`   | This project |
| Team conventions     | `.factory/rules/*.md`    | This project |

### When to Add Memories

| Event                         | What to Record           | Where    |
| ----------------------------- | ------------------------ | -------- |
| Made an architecture decision | Decision + reasoning     | Project  |
| Discovered a preference       | What you prefer          | Personal |
| Learned domain knowledge      | Business rules, entities | Project  |
| Changed your workflow         | New tool or pattern      | Personal |
| Resolved a tricky issue       | Solution and context     | Project  |

### Memory Format Template

```markdown  theme={null}
### [Date]: [Title]
**Decision/Preference**: [What]
**Reasoning**: [Why]
**Context**: [When this applies]
**Trade-offs**: [What you gave up]
```

***

## Next Steps

<CardGroup cols={2}>
  <Card title="Setup Checklist" href="/guides/power-user/setup-checklist" icon="list-check">
    Complete power user configuration
  </Card>

  <Card title="Rules Guide" href="/guides/power-user/rules-conventions" icon="scale-balanced">
    Organize team conventions
  </Card>
</CardGroup>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Rules and Conventions

> Organize coding standards and team conventions so Droid follows them consistently across all work.

Rules are codified standards that Droid follows every time. Unlike memories (which capture decisions and context), rules define how code should be written. This guide shows you how to organize rules effectively for individuals and teams.

<Info>
  **Works with Factory App:** These conventions work identically in both CLI and [Factory App](/web/getting-started/overview)—Droid reads the same `.factory/rules/` files regardless of interface.
</Info>

***

## Rules vs Other Configuration

| Type          | Purpose                    | Example                                            |
| ------------- | -------------------------- | -------------------------------------------------- |
| **Rules**     | How code should be written | "Use early returns instead of nested conditionals" |
| **Memory**    | What was decided and why   | "We chose Zustand because Redux was too verbose"   |
| **AGENTS.md** | How to build/test/run      | "Run `npm test` before completing work"            |
| **Skills**    | How to do specific tasks   | "Steps to implement a new API endpoint"            |

Rules are **prescriptive**—they tell Droid what to do. Use them for standards that should apply consistently.

***

## Setting Up a Rules Directory

### Basic Structure

Create a `.factory/rules/` directory in your project:

```
.factory/
└── rules/
    ├── typescript.md      # TypeScript conventions
    ├── react.md           # React patterns
    ├── testing.md         # Testing requirements
    ├── api.md             # API design rules
    └── security.md        # Security requirements
```

For personal rules that apply across all projects:

```
~/.factory/
└── rules/
    ├── style.md           # Your personal style
    └── tools.md           # Tool preferences
```

### Referencing Rules in AGENTS.md

Add a section to your `AGENTS.md`:

```markdown  theme={null}
## Coding Standards

Follow the conventions documented in `.factory/rules/`:
- **TypeScript**: `.factory/rules/typescript.md`
- **React**: `.factory/rules/react.md`
- **Testing**: `.factory/rules/testing.md`
- **API Design**: `.factory/rules/api.md`
- **Security**: `.factory/rules/security.md`

When working on a file, check the relevant rules first.
```

***

## Writing Effective Rules

### Rule Structure

Each rule should be:

* **Specific**: Clear enough to follow without interpretation
* **Actionable**: Tells what to do, not just what to avoid
* **Scoped**: States when it applies
* **Justified** (optional): Explains why for complex rules

### Template

```markdown  theme={null}
# [Category] Rules

## [Rule Name]
**Applies to**: [file types, contexts]
**Rule**: [specific instruction]
**Example**: [code showing correct usage]
**Rationale**: [why this matters - optional]
```

***

## Example Rules Files

### TypeScript Rules

Create `.factory/rules/typescript.md`:

````markdown  theme={null}
# TypeScript Rules

## Type Definitions

### Use `interface` for object shapes
**Applies to**: All type definitions for objects
**Rule**: Use `interface` for object types, `type` for unions, intersections, and primitives.

```typescript
// ✅ Correct
interface User {
  id: string;
  name: string;
}

type Status = 'active' | 'inactive';
type UserWithStatus = User & { status: Status };

// ❌ Avoid
type User = {
  id: string;
  name: string;
};
````

### Avoid `any`

**Applies to**: All TypeScript files
**Rule**: Never use `any`. Use `unknown` with type guards, or define proper types.

```typescript  theme={null}
// ✅ Correct
function processData(data: unknown): string {
  if (typeof data === 'string') {
    return data.toUpperCase();
  }
  throw new Error('Expected string');
}

// ❌ Avoid
function processData(data: any): string {
  return data.toUpperCase();
}
```

## Function Patterns

### Use early returns

**Applies to**: All functions with conditionals
**Rule**: Return early for edge cases instead of nesting.

```typescript  theme={null}
// ✅ Correct
function processUser(user: User | null): string {
  if (!user) return 'No user';
  if (!user.active) return 'User inactive';
  return `Processing ${user.name}`;
}

// ❌ Avoid
function processUser(user: User | null): string {
  if (user) {
    if (user.active) {
      return `Processing ${user.name}`;
    } else {
      return 'User inactive';
    }
  } else {
    return 'No user';
  }
}
```

### Named exports over default

**Applies to**: All module exports
**Rule**: Use named exports for better refactoring and import clarity.

```typescript  theme={null}
// ✅ Correct
export function createUser() {}
export const USER_ROLES = ['admin', 'user'] as const;

// ❌ Avoid
export default function createUser() {}
```

````

### React Rules

Create `.factory/rules/react.md`:

```markdown
# React Rules

## Component Structure

### Functional components only
**Applies to**: All React components
**Rule**: Use functional components with hooks. Never use class components.

### Props interface naming
**Applies to**: All components with props
**Rule**: Name props interface as `{ComponentName}Props`.

```tsx
// ✅ Correct
interface UserCardProps {
  user: User;
  onSelect: (user: User) => void;
}

export function UserCard({ user, onSelect }: UserCardProps) {
  return <div onClick={() => onSelect(user)}>{user.name}</div>;
}
````

### Component file structure

**Applies to**: All component files
**Rule**: Order sections as: imports, types, component, exports.

```tsx  theme={null}
// 1. Imports (React, external, internal, types)
import { useState } from 'react';
import { Button } from '@/components/ui';
import type { User } from '@/types';

// 2. Types
interface UserListProps {
  users: User[];
}

// 3. Component
export function UserList({ users }: UserListProps) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}
```

## State Management

### Zustand for client state

**Applies to**: Client-side state that isn't server data
**Rule**: Use Zustand stores in `src/stores/`. One store per domain.

```typescript  theme={null}
// src/stores/useUserStore.ts
import { create } from 'zustand';

interface UserState {
  currentUser: User | null;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  currentUser: null,
  setUser: (user) => set({ currentUser: user }),
  logout: () => set({ currentUser: null }),
}));
```

### React Query for server state

**Applies to**: All data fetched from APIs
**Rule**: Use React Query. Queries go in `src/queries/`.

```typescript  theme={null}
// src/queries/useUsers.ts
import { useQuery } from '@tanstack/react-query';

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => fetch('/api/users').then(r => r.json()),
  });
}
```

````

### Testing Rules

Create `.factory/rules/testing.md`:

```markdown
# Testing Rules

## File Organization

### Colocate test files
**Applies to**: All tests except E2E
**Rule**: Place test files next to source files.

````

src/
└── components/
└── UserCard/
├── UserCard.tsx
├── UserCard.test.tsx    # ✅ Colocated
└── index.ts

````

### E2E tests in dedicated directory
**Applies to**: End-to-end tests
**Rule**: Place E2E tests in `e2e/` at project root.

## Test Structure

### Descriptive test names
**Applies to**: All test cases
**Rule**: Format as "should [action] when [condition]".

```typescript
// ✅ Correct
it('should display error message when login fails', () => {});
it('should redirect to dashboard when login succeeds', () => {});

// ❌ Avoid
it('login error', () => {});
it('works', () => {});
````

### One assertion per test

**Applies to**: Unit tests
**Rule**: Test one behavior per test case. Multiple assertions OK if testing same behavior.

```typescript  theme={null}
// ✅ Correct - testing one behavior
it('should format user name correctly', () => {
  const result = formatUserName({ first: 'John', last: 'Doe' });
  expect(result).toBe('John Doe');
});

// ✅ Also correct - same behavior, multiple aspects
it('should return complete user object', () => {
  const user = createUser('John');
  expect(user.id).toBeDefined();
  expect(user.name).toBe('John');
  expect(user.createdAt).toBeInstanceOf(Date);
});

// ❌ Avoid - testing multiple behaviors
it('should handle user operations', () => {
  expect(createUser('John').name).toBe('John');
  expect(deleteUser('123')).toBe(true);
  expect(listUsers()).toHaveLength(0);
});
```

## Mocking

### Mock at boundaries

**Applies to**: All mocked dependencies
**Rule**: Mock external APIs and services, not internal functions.

```typescript  theme={null}
// ✅ Correct - mock external API
vi.mock('@/lib/api', () => ({
  fetchUser: vi.fn().mockResolvedValue({ id: '1', name: 'John' }),
}));

// ❌ Avoid - mock internal implementation
vi.mock('@/utils/formatName', () => ({
  formatName: vi.fn().mockReturnValue('John'),
}));
```

### Use MSW for API mocking in integration tests

**Applies to**: Integration tests that need API responses
**Rule**: Use Mock Service Worker instead of mocking fetch directly.

```typescript  theme={null}
// ✅ Correct
import { http, HttpResponse } from 'msw';

const handlers = [
  http.get('/api/users', () => {
    return HttpResponse.json([{ id: '1', name: 'John' }]);
  }),
];
```

````

### Security Rules

Create `.factory/rules/security.md`:

```markdown
# Security Rules

## Secrets Management

### Never hardcode secrets
**Applies to**: All code
**Rule**: Use environment variables for all secrets. Never commit secrets.

```typescript
// ✅ Correct
const apiKey = process.env.API_KEY;

// ❌ Never do this
const apiKey = 'sk-1234567890abcdef';
````

### Validate environment variables

**Applies to**: Application startup
**Rule**: Validate required env vars exist at startup.

```typescript  theme={null}
// ✅ Correct
const config = {
  apiKey: requireEnv('API_KEY'),
  dbUrl: requireEnv('DATABASE_URL'),
};

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required env var: ${name}`);
  return value;
}
```

## Input Validation

### Validate all external input

**Applies to**: API routes, form handlers
**Rule**: Use Zod to validate all input from users or external sources.

```typescript  theme={null}
// ✅ Correct
import { z } from 'zod';

const CreateUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
});

export async function createUser(input: unknown) {
  const data = CreateUserSchema.parse(input);
  // data is now typed and validated
}
```

## Error Handling

### Never expose internal errors

**Applies to**: API error responses
**Rule**: Log detailed errors server-side; return generic messages to clients.

```typescript  theme={null}
// ✅ Correct
try {
  await processPayment(data);
} catch (error) {
  console.error('Payment failed:', error); // Detailed log
  throw new ApiError('Payment processing failed', 500); // Generic message
}
```

## Authentication

### Check authentication on every protected route

**Applies to**: All API routes requiring auth
**Rule**: Use middleware or guards. Never assume auth from client.

```typescript  theme={null}
// ✅ Correct
export async function GET(request: Request) {
  const session = await getSession(request);
  if (!session) {
    return new Response('Unauthorized', { status: 401 });
  }
  // ... handle authenticated request
}
```

```

---

## Organizing Team Rules

### Layered Rules

For teams, organize rules in layers:

```

.factory/rules/
├── \_base/                    # Foundation rules (everyone follows)
│   ├── typescript.md
│   └── security.md
├── frontend/                 # Frontend-specific
│   ├── react.md
│   └── styling.md
├── backend/                  # Backend-specific
│   ├── api.md
│   └── database.md
└── testing/                  # Testing standards
├── unit.md
└── integration.md

````

Reference in AGENTS.md:

```markdown
## Rules
- Base rules: `.factory/rules/_base/` - Apply to all code
- Frontend rules: `.factory/rules/frontend/` - React components
- Backend rules: `.factory/rules/backend/` - API and services
- Testing rules: `.factory/rules/testing/` - All tests
````

### Rule Ownership

Add ownership to track who maintains each rule set:

```markdown  theme={null}
# TypeScript Rules

**Owner**: Platform Team
**Last Updated**: 2024-02-15
**Review Cycle**: Quarterly

[rules content...]
```

***

## Current Limitation: No Glob Pattern Support

<Warning>
  Currently, Droid doesn't support conditional rule application based on file patterns (e.g., "apply these rules only to `*.tsx` files"). This is on the roadmap.
</Warning>

**Workarounds:**

1. **Organize by file type**: Create separate rules files and reference them contextually

```markdown  theme={null}
# In AGENTS.md
When working on React components (*.tsx), follow `.factory/rules/react.md`
When working on API routes, follow `.factory/rules/api.md`
```

2. **Use clear scoping in rules**: State applicability clearly

```markdown  theme={null}
## This rule applies to: React component files (*.tsx)
```

3. **Use skills for complex workflows**: Skills can encode file-type-specific instructions

***

## Rules Maintenance

### Adding New Rules

When you find yourself correcting Droid repeatedly:

1. Identify the pattern
2. Write a clear rule with examples
3. Add to appropriate rules file
4. Update AGENTS.md if needed
5. Test by asking Droid to do similar work

### Reviewing Rules

Quarterly review checklist:

* [ ] Remove rules that are now enforced by linting
* [ ] Update rules that have changed
* [ ] Add rules for new patterns
* [ ] Check that examples are still accurate
* [ ] Verify AGENTS.md references are current

### Deprecating Rules

When a rule becomes outdated:

```markdown  theme={null}
## ~~Use PropTypes for type checking~~ (DEPRECATED)
**Status**: Deprecated as of 2024-02
**Reason**: We now use TypeScript for all type checking
**Replacement**: See TypeScript rules for prop typing
```

***

## Enforcing Rules Automatically

While Droid follows rules from your `.factory/rules/` files, you can add automated enforcement with [hooks](/cli/configuration/hooks-guide).

### Run Linters After Edits

Add a PostToolUse hook to run your linter after every file edit:

```json  theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$FACTORY_PROJECT_DIR\" && npm run lint -- --fix 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

### Validate Code Style

Run Prettier or your formatter automatically:

```json  theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$FACTORY_PROJECT_DIR\" && npx prettier --write \"$(jq -r '.tool_input.file_path')\" 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

<Tip>
  See [Auto-formatting hooks](/guides/hooks/auto-formatting) and [Code Validation hooks](/guides/hooks/code-validation) for more examples.
</Tip>

***

## Quick Reference

### File Locations

| Scope    | Location            | Use For                |
| -------- | ------------------- | ---------------------- |
| Personal | `~/.factory/rules/` | Your style preferences |
| Project  | `.factory/rules/`   | Team standards         |

### Rule Format

```markdown  theme={null}
## [Rule Name]
**Applies to**: [scope]
**Rule**: [what to do]
**Example**: [code]
**Rationale**: [why - optional]
```

### Good Rules Are

* ✅ Specific and unambiguous
* ✅ Include code examples
* ✅ State when they apply
* ✅ Actionable (do X, not "consider X")
* ❌ Not vague ("write clean code")
* ❌ Not duplicating linter rules
* ❌ Not contradicting other rules

***

## Next Steps

<CardGroup cols={2}>
  <Card title="Setup Checklist" href="/guides/power-user/setup-checklist" icon="list-check">
    Complete power user configuration
  </Card>

  <Card title="Memory Management" href="/guides/power-user/memory-management" icon="brain">
    Capture decisions and context
  </Card>
</CardGroup>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Prompt Crafting for Different Models

> Model-specific prompting techniques to get better results from Claude, GPT, and other models.

Different AI models respond better to different prompting styles. This guide covers model-specific techniques and provides ready-to-use prompt refiner skills.

<Info>
  **Works everywhere:** These prompting techniques apply to both CLI and [Factory App](/web/getting-started/overview).
</Info>

***

## Universal Prompting Principles

These principles work across all models:

<AccordionGroup>
  <Accordion title="Be specific about the outcome">
    **Weak:** "Fix the bug in auth"

    **Strong:** "Fix the login timeout bug where users get logged out after 5 minutes of inactivity. The session should persist for 24 hours."
  </Accordion>

  <Accordion title="Provide context before instructions">
    **Weak:** "Add error handling"

    **Strong:** "This API endpoint handles payment processing. It currently crashes silently on network errors. Add error handling that logs the error, returns a user-friendly message, and triggers an alert."
  </Accordion>

  <Accordion title="Include acceptance criteria">
    **Weak:** "Make it faster"

    **Strong:** "Optimize the search query. Success criteria: query time under 100ms for 10k records, no change to result accuracy, passes existing tests."
  </Accordion>

  <Accordion title="Specify constraints explicitly">
    **Weak:** "Refactor this code"

    **Strong:** "Refactor this code to use the repository pattern. Constraints: don't change the public API, maintain backward compatibility, keep the same test coverage."
  </Accordion>
</AccordionGroup>

***

## Claude Models (Opus, Sonnet, Haiku)

Claude models excel with structured, explicit instructions and respond particularly well to certain formatting patterns.

### Key Techniques for Claude

<Steps>
  <Step title="Use XML tags for structure">
    Claude responds exceptionally well to XML-style tags for organizing complex prompts:

    ```
    <context>
    This is a React application using TypeScript and Zustand for state management.
    The auth module handles user sessions and JWT tokens.
    </context>

    <task>
    Add a "remember me" checkbox to the login form that extends session duration to 30 days.
    </task>

    <requirements>
    - Store preference in localStorage
    - Update JWT expiration accordingly
    - Add unit tests for the new functionality
    </requirements>
    ```
  </Step>

  <Step title="Put examples in dedicated sections">
    When you want specific output formats, show examples:

    ```
    <example>
    Input: "user not found"
    Output: { code: "USER_NOT_FOUND", message: "The specified user does not exist", httpStatus: 404 }
    </example>

    Now handle these error cases following the same pattern:
    - Invalid password
    - Account locked
    - Session expired
    ```
  </Step>

  <Step title="Use thinking prompts for complex reasoning">
    For complex decisions, ask Claude to think through options:

    ```
    Before implementing, analyze:
    1. What are the tradeoffs between approach A and B?
    2. Which approach better fits our existing patterns?
    3. What edge cases should we consider?

    Then implement the better approach.
    ```
  </Step>
</Steps>

<Tip>
  Ready-to-use prompt refiner skills are available in the [examples folder](https://github.com/Factory-AI/factory/tree/main/examples/power-user-skills). Copy them to `~/.factory/skills/` to use them. Learn more about skills in the [Skills documentation](/cli/configuration/skills).
</Tip>

### Claude Prompt Refiner Skill

Create `~/.factory/skills/prompt-refiner-claude/SKILL.md`:

```markdown  theme={null}
---
name: prompt-refiner-claude
description: Refine prompts for Claude models (Opus, Sonnet, Haiku) using Anthropic's best practices. Use when preparing complex tasks for Claude.
---

# Claude Prompt Refiner

## When to Use
Invoke this skill when you have a task for Claude that:
- Involves multiple steps or files
- Requires specific output formatting
- Needs careful reasoning or analysis
- Would benefit from structured context

## Refinement Process

### 1. Analyze the Draft Prompt
Review the user's prompt for:
- [ ] Clear outcome definition
- [ ] Sufficient context
- [ ] Explicit constraints
- [ ] Success criteria

### 2. Apply Claude-Specific Patterns

**Structure with XML tags:**
- `<context>` - Background information, codebase state
- `<task>` - The specific action to take
- `<requirements>` - Must-have criteria
- `<constraints>` - Limitations and boundaries
- `<examples>` - Sample inputs/outputs if helpful

**Ordering matters:**
1. Context first (what exists)
2. Task second (what to do)
3. Requirements third (how to do it)
4. Examples last (clarifying edge cases)

### 3. Enhance for Reasoning
For complex tasks, add:
- "Think through the approach before implementing"
- "Consider these edge cases: ..."
- "Explain your reasoning for key decisions"

### 4. Output the Refined Prompt
Present the improved prompt with:
- Clear section headers
- XML tags where beneficial
- Specific, measurable criteria

## Example Transformation

**Before:**
"Add caching to the API"

**After:**
```

<context>
  The /api/products endpoint currently queries the database on every request.
  Average response time is 200ms. We use Redis for other caching in the app.
</context>

<task>
  Add Redis caching to the /api/products endpoint to reduce database load.
</task>

<requirements>
  * Cache TTL of 5 minutes
  * Cache invalidation when products are updated
  * Graceful fallback to database if Redis is unavailable
  * Add cache hit/miss metrics logging
</requirements>

<constraints>
  * Don't change the response format
  * Must pass existing integration tests
  * Use our existing Redis connection from src/lib/redis.ts
</constraints>

```
```

***

## GPT Models (GPT-5, GPT-5.1, Codex)

GPT models excel with clear system-level context and benefit from explicit role framing.

### Key Techniques for GPT

<Steps>
  <Step title="Frame the role explicitly">
    GPT models respond well to clear role definitions:

    ```
    You are a senior TypeScript developer reviewing code for a production e-commerce platform.
    Focus on: type safety, error handling, and performance.

    Review this checkout flow implementation...
    ```
  </Step>

  <Step title="Use numbered steps for procedures">
    GPT follows numbered instructions reliably:

    ```
    Complete these steps in order:
    1. Read the current implementation in src/auth/
    2. Identify all places where tokens are validated
    3. Create a centralized token validation utility
    4. Update all call sites to use the new utility
    5. Add unit tests for the utility
    6. Run the test suite and fix any failures
    ```
  </Step>

  <Step title="Be explicit about output format">
    Specify exactly what you want:

    ```
    Return your analysis as a markdown document with these sections:
    ## Summary (2-3 sentences)
    ## Issues Found (bulleted list)
    ## Recommended Changes (numbered, in priority order)
    ## Code Examples (if applicable)
    ```
  </Step>
</Steps>

### GPT Prompt Refiner Skill

Create `~/.factory/skills/prompt-refiner-gpt/SKILL.md`:

```markdown  theme={null}
---
name: prompt-refiner-gpt
description: Refine prompts for GPT models (GPT-5, GPT-5.1, Codex) using OpenAI's best practices. Use when preparing complex tasks for GPT.
---

# GPT Prompt Refiner

## When to Use
Invoke this skill when you have a task for GPT that:
- Requires a specific persona or expertise
- Involves procedural steps
- Needs structured output
- Benefits from explicit examples

## Refinement Process

### 1. Analyze the Draft Prompt
Review for:
- [ ] Clear role/persona definition
- [ ] Step-by-step breakdown (if procedural)
- [ ] Output format specification
- [ ] Concrete examples

### 2. Apply GPT-Specific Patterns

**Role framing:**
Start with "You are a [specific role] working on [specific context]..."

**Numbered procedures:**
Break complex tasks into numbered steps that build on each other.

**Output specification:**
Be explicit: "Return as JSON", "Format as markdown with headers", etc.

**Chain of thought:**
For reasoning tasks, add: "Think through this step by step."

### 3. Structure the Prompt

**Effective order for GPT:**
1. Role definition (who/what)
2. Context (background info)
3. Task (what to do)
4. Steps (how to do it, if procedural)
5. Output format (what to return)
6. Examples (optional clarification)

### 4. Output the Refined Prompt
Present with:
- Clear role statement
- Numbered steps where applicable
- Explicit output requirements

## Example Transformation

**Before:**
"Review this code for security issues"

**After:**
```

You are a senior security engineer conducting a security audit of a Node.js payment processing service.

Context: This service handles credit card transactions and communicates with Stripe's API. It runs in AWS ECS.

Task: Review the code in src/payments/ for security vulnerabilities.

Steps:

1. Check for proper input validation on all endpoints
2. Verify secrets are not hardcoded or logged
3. Review authentication and authorization logic
4. Check for SQL injection and XSS vulnerabilities
5. Verify proper error handling that doesn't leak sensitive info

Output format:
Return a security report in markdown with:

* **Critical**: Issues that must be fixed before deployment
* **High**: Significant risks that should be addressed soon
* **Medium**: Improvements to consider
* **Recommendations**: General security enhancements

For each issue, include:

* File and line number
* Description of the vulnerability
* Recommended fix with code example

```
```

***

## Gemini Models

Gemini models handle long context well and work effectively with structured reasoning.

### Key Techniques for Gemini

<Steps>
  <Step title="Leverage long context">
    Gemini can handle extensive context—don't be afraid to include more background:

    ```
    Here's the full module structure for context:
    [include relevant files]

    Based on these patterns, implement a new service that...
    ```
  </Step>

  <Step title="Use reasoning levels effectively">
    Gemini supports Low and High reasoning. Use High for:

    * Architecture decisions
    * Complex debugging
    * Multi-step planning

    Use Low for:

    * Straightforward implementations
    * Code generation from specs
    * Routine refactoring
  </Step>
</Steps>

***

## Model Selection Strategy

Match the model to the task:

| Task Type                   | Recommended Model           | Reasoning Level |
| --------------------------- | --------------------------- | --------------- |
| **Complex architecture**    | Opus 4.5                    | Medium-High     |
| **Feature implementation**  | Sonnet 4.5 or GPT-5.1-Codex | Medium          |
| **Quick edits, formatting** | Haiku 4.5                   | Off/Low         |
| **Code review**             | GPT-5.1-Codex-Max           | High            |
| **Bulk automation**         | GLM-4.6 (Droid Core)        | None            |
| **Research/analysis**       | Gemini 3 Pro                | High            |

***

## Creating Your Own Prompt Refiner

For team-specific needs, create a custom prompt refiner:

```markdown  theme={null}
---
name: prompt-refiner-team
description: Refine prompts using our team's conventions and project context.
---

# Team Prompt Refiner

## Our Conventions
- We use the repository pattern
- All services have interfaces defined first
- Tests use our custom test utilities from @/test-utils

## Checklist for Prompts
1. [ ] References relevant existing code
2. [ ] Specifies which layer (API, service, repository)
3. [ ] Mentions related tests to update
4. [ ] Includes acceptance criteria

## Template
```

Context: \[What exists, what module/layer]
Task: \[Specific action]
Patterns to follow: \[Reference existing similar code]
Tests: \[What tests to add/update]
Done when: \[Acceptance criteria]

```
```

***

## Quick Reference Card

### Claude (Opus/Sonnet/Haiku)

* ✅ XML tags for structure
* ✅ Context before instructions
* ✅ Examples in dedicated sections
* ✅ "Think through..." for reasoning

### GPT (GPT-5/Codex)

* ✅ Role framing ("You are a...")
* ✅ Numbered step procedures
* ✅ Explicit output format
* ✅ "Step by step" for reasoning

### Gemini

* ✅ Extensive context inclusion
* ✅ Low/High reasoning levels
* ✅ Structured output requests

***

## Next Steps

<CardGroup cols={2}>
  <Card title="Setup Checklist" href="/guides/power-user/setup-checklist" icon="list-check">
    Complete power user configuration
  </Card>

  <Card title="Token Efficiency" href="/guides/power-user/token-efficiency" icon="gauge-high">
    Reduce costs while maintaining quality
  </Card>
</CardGroup>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Token Efficiency Strategies

> Reduce token usage while maintaining quality through project setup, model selection, and workflow optimization.

Token usage isn't just about cost—it's about feedback loop speed and context window limits. This guide shows you how to get more done with fewer tokens through project optimization, smart model selection, and workflow patterns.

<Info>
  **Using Factory App?** These strategies apply to both CLI and [Factory App](/web/getting-started/overview). You can view your project's readiness score in the [Agent Readiness Dashboard](/web/agent-readiness/dashboard).
</Info>

***

## Understanding Token Usage

Tokens are consumed in three main areas:

```
┌──────────────────────────────────────────────────────────┐
│                    Token Consumption                      │
├────────────────┬────────────────┬────────────────────────┤
│   Context      │   Tool Calls   │   Model Output         │
│   (Input)      │   (Overhead)   │   (Response)           │
├────────────────┼────────────────┼────────────────────────┤
│ • AGENTS.md    │ • Read files   │ • Explanations         │
│ • Memories     │ • Grep/search  │ • Generated code       │
│ • Conversation │ • Execute cmds │ • Analysis             │
│ • File content │ • Each retry   │ • Thinking tokens      │
└────────────────┴────────────────┴────────────────────────┘
```

**High token usage often means:**

* Too much exploration (unclear instructions)
* Multiple attempts (missing context or failing tests)
* Verbose output (no format constraints)

***

## Project Setup for Efficiency

The biggest token savings come from project configuration that prevents wasted cycles.

### 1. Fast, Reliable Tests

<Warning>
  Slow or flaky tests are the #1 cause of wasted tokens. Each retry costs a full response cycle.
</Warning>

| Test Characteristic | Impact on Tokens                                     |
| ------------------- | ---------------------------------------------------- |
| Fast tests (\< 30s) | Droid verifies changes immediately                   |
| Slow tests (> 2min) | Droid may skip verification or waste context waiting |
| Flaky tests         | False failures cause debugging cycles                |
| No tests            | Droid can't verify changes, more back-and-forth      |

**Action items:**

```markdown  theme={null}
## In your AGENTS.md

## Testing
- Run single file: `npm test -- path/to/file.test.ts`
- Run fast smoke tests: `npm test -- --testPathPattern=smoke`
- Full suite takes ~3 minutes, use `--bail` for early exit on failure
```

### 2. Linting and Type Checking

When Droid can catch errors immediately, it fixes them in the same turn instead of waiting for you to report them.

```markdown  theme={null}
## In your AGENTS.md

## Validation Commands
- Lint (auto-fix): `npm run lint:fix`
- Type check: `npm run typecheck`
- Full validation: `npm run validate` (lint + typecheck + test)

Always run `npm run lint:fix` after making changes.
```

### 3. Clear Project Structure

Document your file organization so Droid doesn't waste tokens exploring:

```markdown  theme={null}
## In your AGENTS.md

## Project Structure
- `src/components/` - React components (one per file)
- `src/hooks/` - Custom React hooks
- `src/services/` - API and business logic
- `src/types/` - TypeScript type definitions
- `tests/` - Test files mirror src/ structure

When adding a new component:
1. Create component in `src/components/ComponentName/`
2. Add index.ts for exports
3. Add ComponentName.test.tsx in same directory
```

***

## Agent Readiness Checklist

The [Agent Readiness Report](/cli/features/readiness-report) evaluates your project against criteria that directly impact token efficiency.

### High-Impact Criteria

| Criterion                       | Token Impact | Why It Matters                                  |
| ------------------------------- | ------------ | ----------------------------------------------- |
| **Linter Configuration**        | 🟢 High      | Catches errors immediately, no debugging cycles |
| **Type Checker**                | 🟢 High      | Prevents runtime errors, clearer code           |
| **Unit Tests Runnable**         | 🟢 High      | Verification in same turn                       |
| **AGENTS.md**                   | 🟢 High      | Context upfront, less exploration               |
| **Build Command Documentation** | 🟡 Medium    | No guessing, fewer failed attempts              |
| **Dependencies Pinned**         | 🟡 Medium    | Reproducible builds                             |
| **Pre-commit Hooks**            | 🟡 Medium    | Automatic quality enforcement                   |

Run the readiness report to identify gaps:

```bash  theme={null}
droid
> /readiness-report
```

***

## Model Selection Strategy

Different models have different cost multipliers and capabilities. Match the model to the task:

### Cost Multipliers

| Model                   | Multiplier | Best For                           |
| ----------------------- | ---------- | ---------------------------------- |
| GLM-4.6 (Droid Core)    | 0.25×      | Bulk automation, simple tasks      |
| Claude Haiku 4.5        | 0.4×       | Quick edits, routine work          |
| GPT-5.1 / GPT-5.1-Codex | 0.5×       | Implementation, debugging          |
| Gemini 3 Pro            | 0.8×       | Research, analysis                 |
| Claude Sonnet 4.5       | 1.2×       | Balanced quality/cost              |
| Claude Opus 4.5         | 2×         | Complex reasoning, architecture    |
| Claude Opus 4.1         | 6×         | Maximum capability (use sparingly) |

### Task-Based Model Selection

```
Simple edit, formatting      → Haiku 4.5 (0.4×)
Implement feature from spec  → GPT-5.1-Codex (0.5×)
Debug complex issue          → Sonnet 4.5 (1.2×)
Architecture planning        → Opus 4.5 (2×)
Bulk file processing         → Droid Core (0.25×)
```

### Reasoning Effort Impact

Higher reasoning = more "thinking" tokens but often fewer retries.

| Reasoning | When to Use              | Token Trade-off                      |
| --------- | ------------------------ | ------------------------------------ |
| Off/None  | Simple, clear tasks      | Lowest per-turn, may need more turns |
| Low       | Standard implementation  | Good balance                         |
| Medium    | Complex logic, debugging | Higher per-turn, fewer retries       |
| High      | Architecture, analysis   | Highest per-turn, best first-attempt |

**Rule of thumb:** Use higher reasoning for tasks where a wrong first attempt would be expensive to fix.

<Tip>
  **Configure mixed models** to automatically use different models for planning vs implementation. See [Mixed Models](/cli/configuration/mixed-models) for setup.
</Tip>

***

## Workflow Patterns for Efficiency

### Pattern 1: Spec Mode for Complex Work

Use [Specification Mode](/cli/user-guides/specification-mode) (`Shift+Tab` or `/spec`) to plan before implementing.

**Without Spec Mode:**

```
Turn 1: Start implementing → wrong approach → wasted tokens
Turn 2: Undo and try different approach → more tokens
Turn 3: Finally get it right
Total: 3 turns of implementation tokens
```

**With Spec Mode:**

```
Turn 1: Plan with exploration → correct approach identified
Turn 2: Implement correctly
Total: 1 turn of planning + 1 turn of implementation
```

<Tip>
  Use Spec Mode (`Shift+Tab` or `/spec`) for any task that:

  * Touches more than 2 files
  * Requires understanding existing patterns
  * Has unclear requirements
  * Is security-sensitive
</Tip>

### Pattern 2: IDE Plugin for Context

Without IDE plugin, Droid must read files to understand context:

```
Read file A → Read file B → Read file C → Understand context → Work
(4 tool calls before actual work)
```

With IDE plugin, context is immediate:

```
Work (IDE provides open files, errors, selection)
(0 extra tool calls for context)
```

### Pattern 3: Specific Over General

**Expensive prompt:**

```
"Fix the bug in the auth module"
```

→ Droid reads multiple files to find the bug, explores different possibilities

**Efficient prompt:**

```
"Fix the timeout bug in src/auth/session.ts line 45 where the session expires after 5 minutes instead of 24 hours"
```

→ Droid goes directly to the issue

### Pattern 4: Batch Similar Work

**Expensive:**

```
Turn 1: "Add logging to userService"
Turn 2: "Add logging to orderService"
Turn 3: "Add logging to paymentService"
(3 turns, context rebuilt each time)
```

**Efficient:**

```
Turn 1: "Add structured logging to all services in src/services/. Use the pattern from src/lib/logger.ts. Services: user, order, payment."
(1 turn, pattern established once)
```

***

## Reducing Token Waste

### Common Waste Patterns

| Pattern                     | Cause                | Fix                    |
| --------------------------- | -------------------- | ---------------------- |
| Multiple exploration cycles | Unclear requirements | Be specific upfront    |
| Repeated file reads         | Missing IDE context  | Install IDE plugin     |
| Failed attempts             | No tests/linting     | Add validation tools   |
| Verbose explanations        | No format constraint | Ask for concise output |
| Wrong architecture          | Missing context      | Use Spec Mode          |

### Format Constraints

Ask for specific output formats to reduce verbosity:

```
"Add the feature. Return only the changed code, no explanations unless something is unclear."
```

```
"Review this code. Format: bullet list of issues only, no preamble."
```

```
"Debug this test failure. Show me the fix, then explain in 2-3 sentences."
```

***

## Monitoring Your Usage

### Check Current Session Cost

```bash  theme={null}
droid
> /cost
```

This shows token usage for the current session.

### Track Over Time

Review your usage patterns:

1. **After each session**, note the `/cost` output
2. **Identify expensive sessions**: What made them expensive?
3. **Refine approach**: More context? Different model? Better prompts?

### Usage Red Flags

Watch for these patterns:

* 🚩 **High read count**: Droid is exploring too much (add AGENTS.md context)
* 🚩 **Multiple grep/search calls**: Unclear what to look for (be more specific)
* 🚩 **Repeated similar edits**: Failed attempts (check tests/linting)
* 🚩 **Very long conversations**: Scope creep (break into smaller tasks)

***

## Quick Wins Checklist

Implement these for immediate token savings:

* [ ] **Install IDE plugin** - Eliminates context-gathering tool calls
* [ ] **Create AGENTS.md** - Droid knows build/test commands upfront
* [ ] **Configure linting** - Errors caught immediately
* [ ] **Fast test command** - Verification in same turn
* [ ] **Use Spec Mode** - Prevents expensive false starts
* [ ] **Be specific** - Reduces exploration cycles
* [ ] **Match model to task** - Don't use Opus for simple edits

***

## Token Budget Guidelines

Rough guidelines for common tasks:

| Task Type              | Typical Token Range | Notes                           |
| ---------------------- | ------------------- | ------------------------------- |
| Quick edit             | 5k-15k              | Simple, specific changes        |
| Feature implementation | 30k-80k             | With Spec Mode planning         |
| Complex debugging      | 50k-150k            | May need multiple attempts      |
| Architecture planning  | 20k-50k             | High-reasoning model            |
| Code review            | 30k-60k             | Depends on PR size              |
| Bulk refactoring       | 50k-200k            | Many files, use efficient model |

If you're significantly exceeding these ranges, review the waste patterns above.

***

## Summary: The Token-Efficient Workflow

```
1. Set up your project
   └─ AGENTS.md with commands
   └─ Fast tests
   └─ Linting configured
   └─ IDE plugin installed

2. Start each task right
   └─ Use Spec Mode for complex work
   └─ Be specific about the goal
   └─ Reference existing patterns

3. Choose the right model
   └─ Simple → Haiku/Droid Core
   └─ Standard → Codex/Sonnet
   └─ Complex → Opus (with reasoning)

4. Monitor and adjust
   └─ Check /cost periodically
   └─ Identify expensive patterns
   └─ Refine your approach
```

***

## Next Steps

<CardGroup cols={2}>
  <Card title="Setup Checklist" href="/guides/power-user/setup-checklist" icon="list-check">
    Complete power user configuration
  </Card>

  <Card title="Readiness Report" href="/cli/features/readiness-report" icon="chart-line">
    Evaluate your project's AI-readiness
  </Card>
</CardGroup>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Evaluating Context Compression

> Summary of Factory Research’s evaluation of context compression strategies for long-running AI agent sessions.

This page summarizes Factory Research’s post: **[Evaluating Context Compression for AI Agents](https://factory.ai/news/evaluating-compression)** (Dec 16, 2025).

<Info>
  For the full methodology, charts, and examples, read the original post linked above.
</Info>

***

## TL;DR

* Long-running agent sessions can exceed any model’s context window, so some form of **context compression** is required.
* The key metric isn’t *tokens per request*; it’s **tokens per task** (because missing details force costly re-fetching and rework).
* In Factory’s evaluation, **structured summarization** retained more “continue-the-task” information than OpenAI’s `/responses/compact` and Anthropic’s SDK compression, at similar compression rates.

***

## Why context compression matters

As agent sessions stretch into hundreds/thousands of turns, the full transcript can reach **millions of tokens**. If an agent loses critical state (e.g., the exact endpoint, file paths changed, or the current next step), it often:

* re-reads files it already read
* repeats debugging dead ends
* forgets what changed and where

That costs more time and tokens than the compression saved.

***

## How Factory evaluated “context quality”

Instead of using summary similarity metrics (e.g., ROUGE), Factory used a **probe-based evaluation**:

1. Take real, long-running production sessions.
2. Compress the earlier portion.
3. Ask probes that require remembering specific, task-relevant details from the truncated history.
4. Grade the answers for functional usefulness.

### Probe types

* **Recall**: factual retention (e.g., “What was the original error?”)
* **Artifact**: file tracking (e.g., “Which files did we modify and how?”)
* **Continuation**: task planning (e.g., “What should we do next?”)
* **Decision**: reasoning chain (e.g., “What did we decide and why?”)

### Scoring dimensions

Responses were scored (0–5) by an LLM judge (**GPT-5.2**) across:

* Accuracy
* Context awareness
* Artifact trail
* Completeness
* Continuity
* Instruction following

The judge is blinded to which compression method produced the response.

***

## Compression approaches compared

| Approach      | What it produces                                                                                                                                                                                                                                      | Key trade-off                                                                                                      |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Factory**   | A **structured, persistent summary** with explicit sections (intent, file modifications, decisions, next steps). Updates by summarizing only the newly-truncated span and **merging** into the existing summary (“anchored iterative summarization”). | Slightly larger summaries than the most aggressive compression, but better retention of task-critical details.     |
| **OpenAI**    | `/responses/compact`: an **opaque** compressed representation optimized for reconstruction fidelity.                                                                                                                                                  | Highest compression, but low interpretability (you can’t inspect what was preserved).                              |
| **Anthropic** | Claude SDK built-in compression: detailed structured summaries (often 7–12k chars), regenerated on each compression.                                                                                                                                  | High-quality summaries, but regenerating the whole summary each time can cause drift across repeated compressions. |

***

## Results (high-level)

Factory reports evaluating **36,000+ messages** from production sessions across tasks like PR review, bug fixes, feature implementation, and refactoring.

### Overall scores (0–5)

| Method    |  Overall | Accuracy |  Context | Artifact | Completeness | Continuity | Instruction |
| --------- | -------: | -------: | -------: | -------: | -----------: | ---------: | ----------: |
| Factory   | **3.70** | **4.04** | **4.01** | **2.45** |     **4.44** |   **3.80** |    **4.99** |
| Anthropic |     3.44 |     3.74 |     3.56 |     2.33 |         4.37 |       3.67 |        4.95 |
| OpenAI    |     3.35 |     3.43 |     3.64 |     2.19 |         4.37 |       3.77 |        4.92 |

### Compression ratio vs. quality

The post notes similar compression rates across methods:

* OpenAI: **99.3%** token removal
* Anthropic: **98.7%** token removal
* Factory: **98.6%** token removal

Factory retained \~0.7 percentage points more tokens than OpenAI (kept more context), and scored **+0.35** higher on overall quality.

***

## What Factory says it learned

* **Structure matters**: forcing explicit sections (files/decisions/next steps) reduces the chance that critical details “silently disappear” over time.
* **Compression ratio is a misleading target**: aggressive compression can “save tokens” but lose details that cause expensive rework; optimize for **tokens per task**.
* **Artifact tracking is still hard**: all methods scored low on tracking which files were created/modified/examined (Factory’s best was **2.45/5**), suggesting this may need dedicated state tracking beyond summarization.
* **Probe-based evaluation is closer to agent reality** than text similarity metrics, because it tests whether work can continue effectively.

***

## Related docs

* [Memory and Context Management](/guides/power-user/memory-management)
* [Token Efficiency Strategies](/guides/power-user/token-efficiency)


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt
