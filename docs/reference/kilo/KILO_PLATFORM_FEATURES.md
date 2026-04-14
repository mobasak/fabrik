# Kilo Platform Features

**Last Updated:** 2026-04-14

This document covers Kilo Code platform features accessed through integrations and web interfaces, complementing the CLI-based workflows.

> **See also:** [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) for the HTTP Server API, custom agents, plugins, and full CLI reference.

---

## Table of Contents

1. [Kilo for Slack](#kilo-for-slack)
2. [App Builder](#app-builder)

---

## Kilo for Slack

Kilo for Slack brings Kilo Code directly into your Slack workspace. Ask questions about repositories, request code implementations, or get help with issues—all without leaving Slack.

### What You Can Do

- **Ask questions about repositories** - Get explanations about code, architecture, or implementation details
- **Request code implementations** - Tell the bot to implement fixes or features suggested in Slack threads
- **Get help with debugging** - Share error messages or issues and get AI-powered assistance
- **Collaborate with your team** - Mention the bot in any channel to get help in context

### Prerequisites

Before using Kilo for Slack:

1. **Kilo Code account** with available credits
2. **GitHub Integration** configured via the Integrations tab so Kilo can access your repositories

### Installation

1. Go to the integrations menu in the sidebar on [app.kilo.ai](https://app.kilo.ai)
2. Set up the Slack integration
3. Authorize Kilo to access your Slack workspace

### How to Interact

#### Direct Messages

Message Kilo directly through Slack DMs for private conversations:

1. Find Kilo in your Slack workspace's app list
2. Start a direct message conversation
3. Ask your question or describe what you need

**Ideal for:**
- Private questions about your code
- Sensitive debugging sessions
- Personal productivity tasks

#### Channel Mentions

Mention the bot in any channel where it's been added:

```
@Kilo can you explain how the authentication flow works in our backend?
```

**Great for:**
- Team discussions where AI assistance would help
- Collaborative debugging sessions
- Getting quick answers during code reviews

### Use Cases

#### Ask Questions About Repositories

Get instant answers about your codebase without switching contexts:

```
@Kilo what does the UserService class do in our main backend repo?

@Kilo how is error handling implemented in the payment processing module?
```

#### Implement Fixes from Slack Discussions

When your team identifies an issue or improvement in a Slack thread, ask the bot to implement it:

```
@Kilo based on this thread, can you implement the fix for the
null pointer exception in the order processing service?
```

The bot can:
- Read the context from the thread
- Understand the proposed solution
- Create a branch with the implementation
- Push the changes to your repository

#### Debug Issues

Share error messages or stack traces and get help:

```
@Kilo I'm seeing this error in production:
[paste error message]
Can you help me understand what's causing it?
```

### How It Works

1. **Message Kilo** - Either through DMs or by mentioning it in a channel
2. **Kilo processes your request** - Uses your connected GitHub repositories to understand context
3. **AI generates a response** - Analyzes your request and provides helpful responses
4. **Code changes (if requested)** - Can create pull requests for implementation requests

### Cost

- Kilo Code credits are used when Kilo performs work (model usage, operations, etc.)
- Credit usage is similar to using Kilo Code through other interfaces

### Tips for Best Results

- **Be specific** - The more context you provide, the better the response
- **Reference specific files or functions** - Help the bot understand exactly what you're asking about
- **Use threads** - Keep related conversations in threads for better context
- **Specify the repository** - If you have multiple repos connected, mention which one you're asking about

### Changing the Model

Customize which AI model Kilo uses for generating responses:

1. Go to your Kilo Workspace
2. Navigate to **Integrations > Slack**
3. Select your preferred model for Kilo for Slack
4. Kilo will start using the new model immediately for subsequent requests

**Available Models:** Over 400+ models across different providers.

### Limitations

- Kilo can only access repositories you've connected through the Integrations page
- Complex multi-step implementations may require follow-up messages
- Response times may vary based on the complexity of your request

### Troubleshooting

| Issue | Solution |
|-------|----------|
| **Kilo isn't responding** | Ensure Kilo for Slack is installed in your workspace and has been added to the channel |
| **Kilo can't access my repository** | Verify your GitHub integration is configured correctly in the Integrations tab |
| **Getting incomplete responses** | Try breaking your request into smaller, more specific questions |
| **Kilo doesn't understand my codebase** | Make sure the repository you're asking about is connected and accessible through your GitHub integration |

---

## App Builder

Kilo's App Builder lets you create end-to-end applications through natural language conversation. Describe what you want to build, watch it come to life in real-time preview, and deploy directly from your Kilo dashboard.

### What App Builder Enables

- **Build complete applications** through conversation with AI
- **Live preview** that updates as your app takes shape
- **One-click deployment** to production
- **Iterative refinement** through natural language feedback
- **Export code** to continue development locally or in Cloud Agents

### Prerequisites

- **Active Kilo Code account** - Sign up or log in at [app.kilo.ai](https://app.kilo.ai)

### Cost

- **Pay only for AI model usage** via Kilo Code credits
- Credit consumption varies based on app complexity and number of iterations
- **Deployment hosting included** during limited launch period

### How to Use

1. **Navigate to App Builder** from your Kilo dashboard
2. **Choose an AI Model** for development (e.g., Grok Code Fast 1, Claude Sonnet 4.5, GPT-5.2)
3. **Describe your application** in plain language:
   - What it should do
   - Key features and functionality
   - Design preferences or constraints
4. **Watch the live preview** update as the AI generates your app
5. **Provide feedback** to refine:
   - "Make the header sticky"
   - "Add a dark mode toggle"
   - "Connect this form to a database"
6. **Click Deploy** to push your app live

### How App Builder Works

**When you describe your application:**

1. The AI model interprets your requirements and generates an initial implementation
2. Code is rendered in real-time in the live preview panel
3. You can interact with the preview as if it were the deployed app
4. Each refinement request triggers targeted updates to the codebase
5. The AI maintains context across your entire conversation for coherent iteration
6. Deployment packages your application and provisions hosting automatically

### Example Application Types

#### Web Applications

- Landing pages and marketing sites
- Dashboards and admin panels
- SaaS products and internal tools
- Portfolio sites and blogs

#### Interactive Tools

- Calculators and converters
- Form builders and survey tools
- Data visualization apps
- Productivity utilities

**Anything that can be supported by a Next.js app can be built with App Builder!**

### Perfect For

App Builder is ideal for:

- **Founders** validating ideas quickly without hiring developers
- **Developers** prototyping before committing to full implementation
- **Teams** building internal tools without diverting engineering resources
- **Designers** bringing concepts to life with functional code
- **Anyone** with an app idea but limited coding experience
- **Hackathons** and rapid experimentation where speed matters

### Limitations and Guidance

- Complex enterprise applications may require additional development outside App Builder
- Some advanced integrations (e.g., specific third-party APIs) may need manual configuration
- Live preview reflects most changes instantly, but some updates may require a brief rebuild

---

## See Also

- **[KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md)** - Complete CLI commands and configuration
- **[KILO_AGENT_NAMING.md](KILO_AGENT_NAMING.md)** - Tier-based agent naming convention
- **[README.md](README.md)** - Kilo system overview
- **[Kilo Code Web Dashboard](https://app.kilo.ai)** - Access App Builder and integrations
