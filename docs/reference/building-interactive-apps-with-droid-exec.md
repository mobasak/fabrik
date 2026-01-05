# Building Interactive Apps with Droid Exec

> Learn how to build a chat with X feature using Droid Exec

<iframe className="w-full aspect-video rounded-xl" src="https://youtube.com/embed/pd8fWTwJylw" title="Building Interactive Apps with Droid Exec" frameBorder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen />

## What this doc covers

* How to build a "chat with repo" feature using Factory's Droid Exec in headless mode
* Setting up streaming responses with Server-Sent Events for real-time agent feedback
* Understanding the actual implementation from Factory's official example

<Note>
  For a complete reference on Droid Exec capabilities, see the [Droid Exec Overview](/cli/droid-exec/overview)
</Note>

***

## 1. Pre-requisites and Installation

### Requirements

* Bun (the example uses Bun, but Node.js works too)
* Factory CLI installed (`droid` on your PATH)
* A local repository to chat with

### Installation

```bash  theme={null}
# Install Bun
curl -fsSL https://bun.sh/install | bash

# Install Factory CLI
curl -fsSL https://app.factory.ai/cli | sh

# Sign in to Factory (one-time browser auth)
droid
```

After the browser login, `droid exec` works from your app without needing API keys in code.

### Try the Official Example

```bash  theme={null}
git clone https://github.com/Factory-AI/examples.git
cd examples/droid-chat
bun i
bun dev
```

Open [http://localhost:4000](http://localhost:4000) - you'll see a chat window overlaid on the repo's README.

***

## 2. Why Use Droid Exec?

Building AI features that understand codebases requires orchestrating multiple operations: searching files, reading code, analyzing structure, and synthesizing answers. Without `droid exec`, a question like *"How do we charge for MCP servers?"* would require dozens of API calls and custom logic to search, read, and understand the relevant code.

`droid exec` is Factory's headless CLI mode that handles this autonomously in a single command. It searches codebases, reads files, reasons about code structure, and returns structured JSON output—with built-in safety controls and configurable autonomy levels. Perfect for building chat interfaces, CI/CD automation, or any application that needs codebase intelligence.

***

## 3. How It Works: The Core Pattern

The Factory example uses a simple pattern: spawn `droid exec` with `--output-format debug` and stream the results via Server-Sent Events (SSE).

### Running Droid Exec

```typescript  theme={null}
// Simplified from src/server/chat.ts
function runDroidExec(prompt: string, repoPath: string) {
  const args = ["exec", "--output-format", "debug"];

  // Optional: configure model (defaults to glm-4.6)
  const model = process.env.DROID_MODEL_ID ?? "glm-4.6";
  args.push("-m", model);

  // Optional: reasoning level (off|low|medium|high)
  const reasoning = process.env.DROID_REASONING;
  if (reasoning) {
    args.push("-r", reasoning);
  }

  args.push(prompt);

  return Bun.spawn(["droid", ...args], {
    cwd: repoPath,
    stdio: ["ignore", "pipe", "pipe"]
  });
}
```

### Key Flags Explained

**`--output-format debug`**: Streams structured events as the agent works

* Each tool call (file read, search, etc.) emits an event
* Lets you show real-time progress to users
* Alternative: `--output-format json` for final output only

**`-m` (model)**: Choose your AI model

* `glm-4.6` - Fast, cheap (default)
* `gpt-5-codex` - Most powerful for complex code
* `claude-sonnet-4-5-20250929` - Best balance of speed and capability

**`-r` (reasoning)**: Control thinking depth

* `off` - No reasoning, fastest
* `low` - Light reasoning (default)
* `medium|high` - Deeper analysis, slower

**No `--auto` flag?**: Defaults to read-only (safest)

* Can't modify files, only read/search/analyze
* Perfect for chat applications

<Note>
  See [CLI Reference](/reference/cli-reference) for all flag explanations
</Note>

***

## 4. Building the Chat Feature: Streaming with SSE

The Factory example streams agent activity in real-time using Server-Sent Events. This gives users immediate feedback as the agent searches, reads files, and thinks.

### Server: Streaming SSE Endpoint

```typescript  theme={null}
// Simplified from src/server/chat.ts
export async function handleChatRequest(req: Request): Promise<Response> {
  const { message, history } = await req.json();

  // Get repo info (finds ./repos/<folder>)
  const repoInfo = await getLocalRepoInfo();

  // Build prompt with history
  const prompt = buildPrompt(message, history);

  // Spawn droid exec
  const proc = runDroidExec(prompt, repoInfo.workdir);

  // Create SSE stream
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();

      // Helper to send events
      const send = (event: string, data: any) => {
        controller.enqueue(encoder.encode(`event: ${event}\n`));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      // Read stdout and parse debug events
      const reader = proc.stdout.getReader();
      let buffer = "";

      (async () => {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += new TextDecoder().decode(value);
          buffer = parseAndFlush(buffer, (event, data) => {
            send(event, data);
          });
        }
      })();

      // When process exits, close stream
      proc.exited.then((code) => {
        send("exit", { code });
        controller.close();
      });
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive"
    }
  });
}
```

### Event Types You'll Receive

When `--output-format debug` is used, droid emits events like:

```
event: tool_call
data: {"tool":"grep","args":{"pattern":"MCP"}}

event: assistant_chunk
data: {"text":"I found references to MCP servers in..."}

event: tool_result
data: {"files_found":["src/billing.ts","config/pricing.yml"]}

event: exit
data: {"code":0}
```

### Client: React Hook for SSE

```typescript  theme={null}
// Simplified from src/hooks/useChat.ts
export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);

  const sendMessage = async (text: string, history: Message[]) => {
    // Add user message
    setMessages(prev => [...prev, { role: "user", content: text }]);

    // Start SSE connection
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history })
    });

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let assistantMessage = { role: "assistant", content: "" };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.startsWith("event:")) {
          const event = line.slice(7);
          const dataLine = lines[++i];
          const data = JSON.parse(dataLine.slice(6));

          if (event === "assistant_chunk") {
            // Append to assistant message
            assistantMessage.content += data.text;
            setMessages(prev => {
              const newMessages = [...prev];
              if (newMessages[newMessages.length - 1]?.role !== "assistant") {
                newMessages.push({ ...assistantMessage });
              } else {
                newMessages[newMessages.length - 1] = { ...assistantMessage };
              }
              return newMessages;
            });
          }

          if (event === "exit") {
            // Done
            break;
          }
        }
      }
    }
  };

  return { messages, sendMessage };
}
```

### Real-World Example: The Video

In the demo video, the user asked: *"Can you search for how we charge for MCP servers?"*

Behind the scenes, `droid exec` automatically:

1. **Searched** the codebase with ripgrep for "MCP", "charge", "payment"
2. **Read** relevant files (billing config, pricing logic, env vars)
3. **Analyzed** the code structure to understand the charging flow
4. **Synthesized** a complete answer with file locations, variable names, and implementation details

All streamed in real-time through SSE - no manual orchestration needed.

### Project Structure (from the Example)

```
examples/droid-chat/
├── src/
│   ├── server/
│   │   ├── index.ts       # Bun HTTP server + static files
│   │   ├── chat.ts        # SSE endpoint, runs droid exec
│   │   ├── repo.ts        # Finds local repo in ./repos/
│   │   ├── prompt.ts      # System prompt + history formatting
│   │   └── stream.ts      # Parses debug output, strips paths
│   ├── components/chat/   # React chat UI
│   └── hooks/useChat.ts   # Client-side SSE parsing
├── repos/                 # Your repositories to chat with
│   └── your-repo/
└── public/                # Static assets
```

### Configuration Options

The example supports environment variables:

```bash  theme={null}
# .env
DROID_MODEL_ID=gpt-5-codex  # Default: glm-4.6
DROID_REASONING=low         # Default: low (off|low|medium|high)
PORT=4000                   # Default: 4000
HOST=localhost              # Default: localhost
```

### Best Practices

✅ **Do:**

* Use read-only mode (no `--auto` flag) for user-facing features
* Validate user input before passing to `droid exec`
* Set timeouts (example uses 240 seconds)
* Parse SSE events incrementally for responsive UI
* Strip local file paths from debug output before sending to client

⚠️ **Avoid:**

* Using `--auto medium/high` in production without sandboxing
* Passing unsanitized user input directly to the CLI
* Blocking the main thread while waiting for results

***

## 5. Customization & Extensions

### Swap the Data Source

The example ships with a local repo, but you can easily adapt it:

**PDFs & Documents:**

```typescript  theme={null}
// Extract text from PDFs, write to temp dir, point droid at it
import { pdfToText } from 'pdf-to-text';

const text = await pdfToText('document.pdf');
fs.writeFileSync('/tmp/docs/content.txt', text);
runDroidExec("Summarize this document", '/tmp/docs');
```

**Databases:**

```typescript  theme={null}
// Add database context to prompt
const prompt = `You have access to a PostgreSQL database with these tables:
${JSON.stringify(schema)}

User question: ${message}`;

runDroidExec(prompt, repoPath); // Can read SQL files in repo
```

**Websites:**

```typescript  theme={null}
// Crawl site, save markdown, chat with it
import TurndownService from 'turndown';

const markdown = new TurndownService().turndown(html);
fs.writeFileSync('./repos/site-content/page.md', markdown);
```

### Change Models on the Fly

```typescript  theme={null}
// Let users pick models
function runWithModel(prompt: string, model: string) {
  return Bun.spawn([
    "droid", "exec",
    "-m", model,  // glm-4.6, gpt-5-codex, etc.
    "--output-format", "debug",
    prompt
  ], { cwd: repoPath });
}
```

### Add Tool Call Visibility

The example's `stream.ts` parses debug events. You can surface them in the UI:

```typescript  theme={null}
if (event === "tool_call") {
  // Show: "🔍 Searching for 'MCP charge'"
  // Show: "📄 Reading src/billing.ts"
}
```

This creates a transparent, trust-building experience where users see exactly what the agent is doing.

***

## Additional Resources

**Official Example:**

* [GitHub: droid-chat example](https://github.com/Factory-AI/examples/tree/main/droid-chat) - Full working code

**Documentation:**

* [Droid Exec Overview](/cli/droid-exec/overview) - Complete CLI reference
* [Autonomy Levels Guide](/cli/user-guides/auto-run) - Understanding `--auto` flags
* [CI/CD Cookbook](/guides/droid-exec/code-review) - Production patterns
* [Model Configuration](/reference/cli-reference) - Available models and settings

**Community:**

* [Factory Discord](https://discord.gg/zuudFXxg69) - Get help from the team
* [GitHub Discussions](https://github.com/factory-ai/factory/discussions) - Share your builds

***

## Next Steps

1. Clone the example: `git clone https://github.com/Factory-AI/examples.git`
2. Run it locally: `cd examples/droid-chat && bun dev`
3. Explore the code in `src/server/chat.ts` to see how SSE streaming works
4. Customize `src/server/prompt.ts` to change the agent's behavior
5. Swap `./repos/` content to chat with your own repositories

The example is intentionally minimal (\~500 lines total) so you can understand it fully and adapt it to your needs.


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Deploy Droid on a VPS Server

> Learn how to set up droid on a VPS for remote access and headless automation

<iframe className="w-full aspect-video rounded-xl" src="https://youtube.com/embed/a3tqhTdSugg" title="Deploy Droid on a VPS Server" frameBorder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen />

## What this doc covers

* Set up Factory's CLI, Droid, on a Virtual Private Server (VPS) for remote access from anywhere
* Configure SSH authentication with key pairs for secure, passwordless server connections
* Use `droid exec` for headless automation tasks and system administration on your server

***

## 1. Prerequisites and installation

Before starting, you'll need:

* **Factory CLI installed locally** - Follow the [installation guide](/cli/getting-started/quickstart)
* **Factory account** - Sign up at [factory.ai](https://factory.ai)
* **VPS provider account** - This tutorial uses [Hetzner](https://www.hetzner.com/), but works with any VPS provider (DigitalOcean, Linode, AWS EC2, etc.)
* **Basic terminal familiarity** - You'll be running commands in your local terminal and on the server

**Cost estimate**: A basic VPS suitable for running droid costs around \$5-10/month.

***

## 2. Why use droid on a VPS?

Running AI agents locally limits you to when you're at your computer. Production debugging, scheduled automation, and mobile access all require a server that's always available. Without a VPS, you can't monitor servers from your phone, run headless automation 24/7, or access droid while traveling.

By deploying droid on a VPS, you get an always-available AI assistant accessible from any device. Perfect for system administration, production debugging, and building custom automation workflows with `droid exec`.

***

## 3. Setup and basic usage

Let's walk through the complete setup process, from creating SSH keys to connecting to your VPS.

### Step 1: Generate SSH keys with droid

We'll use droid locally to create an SSH key pair. This is more secure than password authentication and enables seamless connections.

```bash  theme={null}
# Start droid in your local terminal
droid

# Ask droid to create the key pair
> Create a new SSH key pair called example
```

Droid will generate two files:

* `~/.ssh/example` - Private key (keep this secret, never share)
* `~/.ssh/example.pub` - Public key (safe to share, will be added to your VPS)

### Step 2: Copy the public key

```bash  theme={null}
# Ask droid to copy the public key to your clipboard
> Copy the public key to the clipboard
```

### Step 3: Create your VPS and add the SSH key

In your VPS provider dashboard (Hetzner example):

1. **Create a new server**:
   * Choose your server type (e.g., CPX22 - \$4.99/month)
   * Select a location (e.g., Ashburn, Virginia)
   * Keep default options

2. **Add your SSH key**:
   * In the "SSH Keys" section, click "Add SSH Key"
   * Paste the public key you copied
   * Name it "example" (or any descriptive name)
   * Add the key to the server

3. **Name and create**:
   * Optionally name your server (e.g., "example-vps")
   * Click "Create" and wait for the server to spin up

### Step 4: Configure SSH for easy access

Once your server is ready, copy its IP address (e.g., `123.45.67.89`) and ask droid to configure your SSH settings:

```bash  theme={null}
# In droid
> Add 123.45.67.89 to my SSH config file with an alias called example so I can connect easily
```

Droid will update your `~/.ssh/config` file to include something like:

```ssh-config  theme={null}
Host example
    HostName 123.45.67.89
    User root
    IdentityFile ~/.ssh/example
```

**What this enables**: Instead of typing `ssh root@123.45.67.89 -i ~/.ssh/example` every time, you can simply run `ssh example`.

### Step 5: Connect and install Droid on the VPS

```bash  theme={null}
# In a new terminal window, connect to your VPS
ssh example

# Install Factory CLI on the VPS
curl -fsSL https://cli.factory.ai/install.sh | sh

# Activate the installation
source ~/.bashrc  # or source ~/.zshrc if using zsh

# Verify installation
droid --version
```

### Step 6: Authenticate Droid on the VPS

```bash  theme={null}
# Run droid for the first time
droid
```

On first run, droid will prompt you to log in:

1. It displays a URL and an authentication code
2. Copy the code
3. Click the URL (or paste it in your browser)
4. Paste the code to authenticate
5. You're now logged in and can use droid on your VPS

**Success check**: You should now see the droid prompt on your VPS, ready to accept commands.

***

## 4. Advanced example: System administration with droid

Now that droid is running on your VPS, let's use it for practical server administration. This example shows how droid can handle complex setup tasks like configuring a web server.

### Setting up Nginx with Docker

```bash  theme={null}
# In your VPS, with droid running
> Set up Nginx with Docker and serve a hello world page
```

Droid will:

1. Install Docker if not already present
2. Create a basic Nginx configuration
3. Create an HTML file with "Hello World"
4. Set up and run the Docker container
5. Configure networking and ports

**Verification**: Open a browser and navigate to your VPS IP address (e.g., `http://123.45.67.89`). You should see "Hello World" displayed.

**What makes this powerful**: Tasks that normally require multiple commands, configuration files, and troubleshooting are handled by droid with a single natural language instruction. Droid understands best practices and handles edge cases automatically.

***

## 5. Droid exec: Headless automation and custom agents

The real power of running droid on a VPS is `droid exec` - a headless mode that enables programmatic access for building automation workflows and custom agents.

### What is droid exec?

`droid exec` runs droid commands without an interactive session, making it perfect for:

* Scheduled automation tasks
* Building custom agent frameworks
* Integrating droid into scripts and applications
* Running quick queries from CI/CD pipelines

<Note>See the full droid exec docs [here](/cli/droid-exec/overview).</Note>

### Basic droid exec usage

```bash  theme={null}
# Simple query with a fast model (GLM 4.6)
droid exec --model glm-4.6 "Tell me a joke"
```

### Advanced: System exploration

```bash  theme={null}
# Ask droid to explore your system and find specific information
droid exec --model glm-4.6 "Explore my system and tell me where the file is that I'm serving with Nginx"
```

Droid will:

1. Search for Nginx configuration files
2. Identify the document root
3. Locate the HTML/content files being served
4. Report back with file paths and relevant configuration

**Output example**:

```
Configuration file: /etc/nginx/nginx.conf
Content file: /var/www/html/index.html
Docker setup: /home/user/docker-compose.yml
Server running on: port 80
```

***

## 6. Remote access from anywhere

One of the biggest advantages of having droid on a VPS is accessing it from any device, including mobile.

### Using Termius for mobile SSH access

<iframe className="w-full aspect-video rounded-xl" src="https://youtube.com/embed/6aghwvyZsDo" title="Using Termius for mobile SSH access" frameBorder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen />

[Termius](https://termius.com/) is a modern SSH client available for:

* macOS, Windows, Linux (desktop)
* iOS and Android (mobile)

**Setup steps**:

1. **Install Termius** on your device
2. **Add your SSH key**:
   * In Termius, go to Keychain
   * Add a new key
   * Import your private key (`~/.ssh/example`)
3. **Add your VPS host**:
   * Create a new host
   * Hostname: Your VPS IP address
   * Username: `root` (or your configured user)
   * Key: Select the key you imported
4. **Connect**: Tap the host to connect

**Mobile workflow**:

```bash  theme={null}
# On your phone via Termius
ssh example

# Run droid
droid

# Or use droid exec for quick queries
droid exec --model glm-4-flash "Check system resources and uptime"
```

### Real-world scenarios

* **Travel troubleshooting**: Server goes down while you're away? SSH in from your phone and let droid help diagnose and fix the issue
* **On-call debugging**: Respond to alerts from anywhere with AI-assisted investigation
* **Quick queries**: Check system status, review logs, or make configuration changes without needing your laptop

## Next steps

Now that you have droid running on your VPS:

1. **Explore automation**: Start with simple `droid exec` commands and build up to custom scripts
2. **Set up monitoring**: Use droid to help configure system monitoring and alerting
3. **Create scheduled tasks**: Combine droid exec with cron jobs for recurring automation
4. **Join the community**: Share your use cases and learn from others in the [Factory Discord](https://discord.gg/zuudFXxg69)

For more information:

* [Factory CLI Documentation](/cli/getting-started/overview)
* [Droid Exec Reference](/cli/droid-exec/overview)
* [Custom Droids Guide](/cli/configuration/custom-droids)


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt
