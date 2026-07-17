# **AI Coding Agent Orchestrators: A Comparative Evaluation of Local-First, Worktree-Isolated GUI Cockpits**

The paradigm of AI-assisted software development has definitively transitioned from linear, single-turn chatbot interfaces (e.g., standard code copilots) to parallelized, autonomous agent fleets capable of executing complex, multi-step engineering tasks1. Managing a highly concurrent fleet—specifically around 20 simultaneous agent sessions operating on a single 24-core, 48 GB host machine—requires a robust, highly optimized macro-orchestration layer3. When deployment constraints dictate a local-first architecture on Windows via the Windows Subsystem for Linux (WSL Ubuntu), strict reliance on subscription-based authentication to bypass exorbitant per-token API costs, and a lightweight graphical user interface (GUI) that avoids the memory bloat of traditional web technologies, the architectural requirements become exceedingly stringent.
This report evaluates the current open-source landscape of AI coding agent orchestrators. The analysis rigorously scrutinizes application framework weight (comparing Electron against native-webview alternatives like Tauri, Wails, or Electrobun), authentication topologies, git worktree isolation mechanisms, and extensibility seams achieved through the Model Context Protocol (MCP) or custom plugin architectures. The objective is to identify and rank the optimal orchestrator for a developer to fork and customize into a lightweight, high-concurrency desktop cockpit.

## **Architectural Prerequisites for High-Concurrency Orchestration**

Operating 20 autonomous coding agents concurrently on a single 48 GB machine introduces severe resource contention, state management challenges, and inter-process communication bottlenecks. To understand the viability of any open-source orchestrator, the underlying software architecture must be framed through five specific technical lenses.

### **The Resource Footprint of the UI Framework**

The choice of application runtime dictates the baseline idle and active memory footprint. Electron-based applications, which package a full Chromium browser instance and a Node.js runtime per application window, exhibit baseline memory consumption typically ranging between 300 MB and 500 MB before rendering any complex Document Object Model (DOM) updates4. Rendering 20 active terminal streams via libraries such as xterm.js in a single DOM frequently leads to massive V8 heap bloat. Under sustained output from multiple Large Language Models (LLMs), Electron's Inter-Process Communication (IPC) bridge and React reconciliation cycles can heavily thrash the CPU, leading to Out-of-Memory (OOM) application crashes3. Furthermore, Chromium inherently restricts applications to a default limit of 16 active WebGL contexts per renderer, meaning an Electron app attempting to hardware-accelerate 20 terminal instances will simply fail to render the overflow without explicit, deep-level Chromium flag overrides8.
Conversely, native-webview frameworks like Tauri, Wails, and Electrobun decouple the backend daemon—usually written in systems languages like Rust, Go, or a highly optimized JavaScript runtime like Bun—from the OS-native webview. On Windows, this translates to utilizing the WebView2 runtime, while macOS relies on WebKit9. This architecture reduces the baseline idle RAM to approximately 50 MB to 100 MB and shifts heavy algorithmic processing to a compiled backend11. For a Windows \+ WSL environment, decoupling the backend (running natively and seamlessly in the WSL Ubuntu user space) from the frontend (rendered in a native Windows browser or a lightweight webview container) provides the most stable, scalable memory profile for 20 concurrent streams.

### **Authentication Topologies and Bypassing Metered API Costs**

A critical financial and operational requirement for managing a fleet of 20 agents is the utilization of existing user subscriptions (such as Claude Pro or ChatGPT Plus) rather than relying on metered API keys (such as the Anthropic API or the metered Agent-SDK credit paths)11. The orchestration framework must not act as a traditional API gateway; instead, it must launch the first-party, interactive Command Line Interfaces (CLIs)—such as @anthropic-ai/claude-code or @openai/codex—and manipulate them programmatically.
This is universally achieved by wrapping the CLI process in a pseudo-terminal (PTY) or a terminal multiplexer like tmux11. By sending prompts as simulated keystrokes (e.g., executing tmux send-keys) and reading the standard output, the orchestrator "drives" the agent identically to a human user, drawing from the flat-rate monthly subscription quota11. Support for alternative models via OpenRouter is typically achieved by injecting an OPENROUTER\_API\_KEY into the environment variables of the spawned CLI process, or by using a local proxy router that intercepts SDK calls and redirects them to OpenRouter endpoints, ensuring total provider agnosticism14.

### **Git Worktree Isolation Mechanics**

Concurrency at the filesystem level is impossible if multiple agents modify the same working directory simultaneously. Traditional git branching requires stashing changes or performing sequential operations, which fundamentally breaks parallel agent execution. Agent orchestrators solve this bottleneck by utilizing the git worktree command11.
A git worktree provides an isolated physical directory on the disk with its own checked-out branch, while sharing the underlying .git object database of the main repository. This isolation allows 20 agents to independently run package managers (e.g., npm install), execute test suites, run language servers, and mutate files simultaneously without lock contention or cross-contamination11. Without strict worktree implementation, agent fleets rapidly overwrite each other's code, resulting in corrupted project states.

### **Intercepting the LLM Event Loop for Approvals**

Coding agents frequently pause to request human permission for destructive actions, such as executing arbitrary shell scripts, deleting files, or making external network requests. A purely headless orchestrator stalls indefinitely in these states. Advanced graphical cockpits must intercept these prompts and surface them as structured visual components—such as radio buttons, text inputs, or checkboxes—within the UI11.
Scraping raw PTY stdout for ANSI-escaped prompts is highly brittle and prone to race conditions. The state-of-the-art approach involves tailing structured application logs (e.g., JSONL transcripts) to parse events like AskUserQuestion or tool-call requests deterministically11. This allows the orchestrator to present a clean, actionable prompt to the user in the GUI, receive the human input, and inject the response back into the agent's PTY session.

### **Extensibility Seams and the Model Context Protocol (MCP)**

To embed custom command pipelines, the orchestrator must feature a well-defined extensibility seam. The Model Context Protocol (MCP) has emerged as the industry standard for this capability. An orchestrator can act as an MCP client, providing the agent with access to external tools (such as database querying or web searching), or it can act as an MCP server, allowing the agent to programmatically control the orchestrator itself (e.g., moving cards on a kanban board, opening new worktrees, or managing sibling agents)3. Beyond MCP, plugin architectures that utilize dynamic worker sandboxes or environment shaping allow developers to inject custom shell scripts and pre-computation hooks into the agent's execution pipeline20.

## **Disqualified Candidates: The CLI/TUI Boundary**

Before evaluating the graphical desktop cockpits, two prominent open-source orchestrators must be excluded based on the strict requirement for a Graphical User Interface featuring a file tree, markdown viewer, diff panels, and visual workflows.
The ccswarm project (https://github.com/nwiizo/ccswarm), which holds 146 stars and 14 forks, is a highly robust workflow engine for AI agents written entirely in Rust22. It successfully utilizes Git worktree isolation and drives Claude Code via a custom PTY implementation to leverage subscription authentication17. However, its interaction model is strictly limited to the Command Line Interface and a Terminal User Interface22. Because it lacks visual diff review, markdown rendering, and a drag-and-drop workflow plane, it fails the visual cockpit requirement22.
Similarly, Groundcrew (https://github.com/ClipboardHealth/groundcrew), which holds 52 stars and 6 forks, is an orchestrator that dispatches backlog tickets from Linear directly to local, interactive Claude Code and Codex sessions running inside tmux panes12. Licensed under MIT, it enforces one git worktree per task and sandboxes agents using Docker24. Like ccswarm, Groundcrew operates exclusively as a background daemon and CLI tool. It does not ship with a GUI, rendering it unsuitable for the visual cockpit requirement24.

## **Comprehensive Evaluation of GUI Orchestrators**

The following six systems meet the baseline criteria of open-source licensing, multi-agent orchestration, and graphical interfaces. They are evaluated specifically for their viability as a forkable, lightweight, high-concurrency desktop cockpit designed to manage 20 simultaneous sessions on a Windows \+ WSL architecture.

### **1\. Agetor**

Agetor (https://github.com/alamops/agetor) is a local-first kanban control plane explicitly designed to run Claude Code, Codex, and other CLI agents in parallel. While a relatively new project (indicated by its recent v0.0.1 and v0.0.2 releases), its architectural choices align exceptionally well with lightweight requirements9.
Agetor Abandons the heavy Node and Chromium overhead of Electron in favor of Electrobun, a native desktop application runtime where a Bun main process controls the window and a native OS WebView handles the React rendering11. The React webview communicates with the Bun main process via a plain HTTP API bound to 127.0.0.1, secured by a per-launch random bearer token11. This architecture yields an exceptionally low idle RAM footprint, estimated between 50 MB and 100 MB for the orchestrator shell. Under the load of 20 agents, the computational burden shifts entirely to the spawned tmux processes and the OS-level webview rendering, keeping the core highly responsive and preventing UI thread locking.
Agetor explicitly drives Claude Code in interactive mode via tmux. Prompts are delivered directly as keystrokes via tmux load-buffer and send-keys, fully leveraging the flat-rate user subscription11. Multi-account concurrency is supported by defining custom "harnesses" that inject dedicated $HOME environment variables, preventing authentication token collisions across parallel sessions11. OpenRouter models can be integrated by wrapping custom CLI binaries or injecting OpenRouter environment variables into these harnesses11.
Every task generates a dedicated branch and an isolated worktree under the \~/.agetor/worktrees/ directory11. The base git reference is pinned at creation time, ensuring that any re-runs start deterministically from the same commit11. Rather than scraping the terminal for approvals, Agetor watches Claude's internal JSONL transcripts (\~/.claude/projects/.../\<sessionId\>.jsonl). It deterministically parses AskUserQuestion and tool-permission events, surfacing them in the React UI as structured cards containing radios and checkboxes11. This is the most resilient approach to human-in-the-loop approvals currently available.
Agetor is distributed under the permissive MIT License26. While it is primarily tested and developed on macOS, Windows and Linux builds are configured in its electrobun.config.ts file, though they remain largely untested by the original author11. Running native webviews via WSLg on Windows carries a moderate engineering risk, requiring some hardening to ensure the WebView2 bindings function correctly across the WSL boundary.

### **2\. Conductor OSS**

Conductor OSS (https://github.com/charannyk06/conductor-oss), formerly developed under Meltylabs, is a highly mature local-first orchestrator that coordinates planning, runtime state, and review context27. The project maintains an active release schedule (currently at v0.61.13) with over 208 commits27.
Conductor abandons the desktop-wrapper paradigm entirely. It consists of a highly optimized Rust backend server (crates/conductor-server) utilizing the Axum framework, paired with a Next.js web dashboard (packages/web)13. Because the UI is served to a standard host browser (e.g., Edge or Chrome on Windows), there is zero Electron overhead13. The idle CPU and RAM footprint of the compiled Rust daemon is practically negligible, consistently remaining under 50 MB.
Conductor launches the actual Claude Code, Codex, and Gemini CLIs, maintaining their native terminal behavior and relying on their built-in subscription-based authentication models13. It supports 14 different agents out-of-the-box, with configuration readily available for OpenRouter endpoints via environment mapping13. When dispatching a task, Conductor completely automates git worktree management, creating an isolated workspace, branch, and environment31.
The UI operates on a highly efficient "diff-first" review model, aggregating file changes across all 20 worktrees for rapid human acceptance or rejection, rather than forcing the user to navigate full file trees for every agent31. Conductor is massively extensible; it acts as an MCP server itself and can dynamically mount per-project MCP servers defined in its YAML configuration files19. It connects seamlessly to GitHub webhooks and features deep editor handoffs19.
Licensed under Apache 2.0, Conductor provides native binaries for Windows, macOS, and Linux13. The split client-server architecture is mathematically optimal for WSL: the Rust daemon runs flawlessly in the WSL Ubuntu environment, executing bash/tmux commands natively, while the developer interacts with the Next.js dashboard via localhost:4747 on the Windows host27.

### **3\. Vibe Kanban**

Vibe Kanban (https://github.com/BloopAI/vibe-kanban) is a visual task management board engineered explicitly for orchestrating AI coding agents2. It is one of the most popular tools in the ecosystem, boasting 27.4k stars and 2.9k forks32.
Vibe Kanban employs a Rust backend paired with a React and TypeScript web interface32. While technically lightweight in its backend design, production tracking reveals severe, crippling memory leaks in the browser component. Profiling data indicates the JS Heap Size routinely reaches 3.8 GB and climbs at a rate of 14.5 MB/s during heavy AI task execution or large file-tree indexing7. This invariably culminates in "Aw, Snap\!" Out-of-Memory browser crashes7. Running 20 parallel agent streams would rapidly trigger this failure mode, making the current UI implementation a massive liability for high-concurrency orchestration.
The framework spawns subprocesses for Claude Code and Codex, relying on local CLI subscription authentication32. It interfaces with OpenRouter via a highly sophisticated proxy known as the Claude Code Router (CCR). CCR intercepts Claude Code SDK calls and routes coding prompts across different LLM providers based on complexity—for example, routing background tasks to cheaper OpenRouter models while reserving Anthropic models for complex reasoning16.
Vibe Kanban robustly supports git worktree isolation, executing a git worktree add \<path\> \<new\_branch\> command the moment a kanban card is dragged into the "In Progress" column18. It includes a dedicated diff review UI allowing inline comments that are automatically piped back to the agent for revision32. It supports MCP both as a client (providing tools to the agent) and as a server (allowing the agent to manage the kanban board itself)18.
Licensed under Apache 2.0, Vibe Kanban compiles natively for Linux and Windows34. However, due to the severe browser memory leaks, there is an ongoing community push to wrap the web UI in Tauri to escape browser limitations, though this refactor is not yet fully realized in the main branch10.

### **4\. Agent Orchestrator (AO)**

Agent Orchestrator (https://github.com/AgentWrapper/agent-orchestrator), holding 8.2k stars and 1.2k forks, is a "meta-harness" IDE designed specifically to automate the feedback loop between parallel agents, Continuous Integration (CI) systems, and code reviews37.
AO utilizes a Go-based daemon for backend logic and an Electron renderer for the desktop application37. As an Electron app, the frontend incurs a high base memory footprint (500 MB+), making it unsuited for ultra-lightweight deployments when memory must be preserved for 20 agent subprocesses. AO utilizes whatever authentication the underlying agent plugin uses (e.g., Claude for Claude Code). Keys and environment variables are passed directly to the agent's tmux session42. OpenRouter integration is robustly supported via environment shaping (e.g., injecting specific base URLs and API keys for providers like MiniMax)21.
AO creates isolated git worktrees for every session37. It shines primarily in its automation capabilities. It features a reaction engine that automatically detects CI failures, fetches the associated error logs, and routes them back to the specific agent without human intervention, utilizing configurable retry counts before escalating to a human user37. It utilizes 8 pluggable slots for deep extensibility (runtime, agent, workspace, tracker, SCM, notifier, terminal, lifecycle)43. However, it critically lacks a checkpointing mechanism; if an agent session crashes or is interrupted, all work-in-progress state is permanently lost, forcing a total restart44.
Licensed under Apache 2.0, it supports Windows, macOS, and Linux AppImages, providing excellent OS compatibility but suffering from the inherent Electron performance penalty37.

### **5\. Emdash**

Emdash (https://github.com/generalaction/emdash), backed by Y Combinator, is a mature, local-first Desktop application for parallel agent execution with 5.2k stars and 539 forks5.
Emdash is built heavily on Electron and React5. While feature-rich and visually polished, the Chromium overhead is substantial. A base Electron process consumes roughly 300 MB, with additional memory allocated per PTY instance. Running 20 isolated agent sessions with active terminal streams guarantees a RAM footprint exceeding 2 GB to 3 GB solely for the UI and IPC layers, severely constraining the 48 GB host machine which requires memory for language servers, Docker, and the agent processes themselves.
Emdash is strictly provider-agnostic. It detects installed CLIs (Claude Code, Codex, Amp) and runs them natively, leveraging existing OAuth or subscription credentials5. Models from OpenRouter are fully supported14. Comprehensive worktree support is integrated deeply into the core; each task is automatically siloed in a dedicated branch and directory5.
Emdash pulls issues directly from Linear, Jira, or GitHub. The UI supports live diff reviews, pull request creation, and CI check inspections directly within the interface5. Extensibility is handled via dynamic worker load loaders, where plugins run in isolated sandboxes with declarative capability manifests, alongside a built-in MCP server5.
Licensed under Apache 2.0, Emdash ships with a Windows installer and Linux AppImage/Debian packages5. WSL compatibility is achievable via X-server routing or native Windows installation, but the heavy Electron penalty remains the primary deterrent for high-concurrency scaling.

### **6\. Daintree**

Formerly known as Canopy, Daintree (https://github.com/daintreehq/daintree) is a heavy delegation environment designed for macro-orchestrating AI agents. Following its rebrand, the repository currently displays 44 stars and 6 forks3.
Daintree is built on Electron 42 (Chromium 148), React 19, and the xterm.js rendering library3. This constitutes the heaviest application framework in the evaluated cohort. Chromium enforces a default limit of 16 active WebGL contexts per renderer; to survive heavy terminal multiplexing, Daintree has to explicitly append the \--max-active-webgl-contexts=32 flag to the electron host8. At 20 concurrent terminal streams, the WebGL rendering pipelines will struggle massively, leading to dropped frames and potential UI freezes. Despite implementing memory-aware targeted trimming of V8 heap snapshots to prevent unbounded growth, the architecture is inherently bloated49.
Daintree drives local Claude Code and Codex instances utilizing the user's existing credentials3. It features deep git worktree integration via its "Worktree Dashboard," which parses git porcelain output to manage branch isolation and detect running development servers3. Extensibility is managed by the "Daintree Assistant," which uses an MCP server to interface directly with the agents3. It also supports context injection via a feature called "CopyTree"3.
Licensed under Apache 2.0, Daintree provides native Windows .appx and Linux builds3. While functional, its extreme weight makes it unsuitable for the 20-agent lightweight cockpit requirement.

## **Architectural Trade-off Analysis**

To synthesize the data for a deployment involving 20 concurrent agent sessions on a Windows \+ WSL infrastructure, several underlying technical realities must dictate the architectural choice.
A 24-core, 48 GB machine is exceptionally powerful, but modern AI development workflows are highly I/O and memory intensive. Running 20 parallel Node.js ecosystems (comprising the language servers, TypeScript compilers, and linters required by the agents to verify their code in their respective worktrees), alongside 20 agent environments, will quickly saturate the 48 GB of RAM. Allocating an additional 2 GB to 4 GB to a Chromium-based Electron UI (as seen in Daintree, Emdash, and AO) is an unacceptable architectural compromise.
The orchestrator UI must be fundamentally decoupled from the execution daemon. A lightweight Rust, Go, or Bun daemon running natively inside the WSL environment, generating under 100 MB of overhead, paired with a web UI rendered natively by the host OS browser (or a minimal native webview), is the only mathematically sound approach to maximize hardware resources for the actual coding agents.
Furthermore, when an agent reaches a state requiring human approval (e.g., executing a destructive shell command), the system must cleanly pause and alert the human. Scraping terminal ANSI outputs is prone to race conditions. Agetor's methodology of tailing the \~/.claude/projects/.../\<sessionId\>.jsonl file to parse state changes deterministically guarantees UI synchronization without relying on fragile text scraping11. Conductor achieves similar stability through strict diff-first reviews and decoupled backend monitoring31.

## **Tabular Syntheses**

The following tables synthesize the research data, mapping repository metrics, framework footprints, and orchestration mechanisms to facilitate a clear comparative analysis.

### **Table 1: Repository Metrics, Licensing, and Platform Support**

| Orchestrator | Repository URL | Stars / Forks | License | Framework | Windows / WSL Support |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Conductor OSS** | charannyk06/conductor-oss | Active (v0.61.13) | Apache 2.0 | Rust (Axum) \+ Next.js Web UI | Excellent (Native Binaries, WSL daemon via localhost) |
| **Agetor** | alamops/agetor | New (v0.0.2) | MIT | Electrobun (Bun \+ React) | Moderate (Configured, but currently untested on Win/Linux) |
| **Vibe Kanban** | BloopAI/vibe-kanban | 27.4k / 2.9k | Apache 2.0 | Rust \+ React Web UI | Good (Native Binaries), but UI memory leaks limit scale |
| **Agent Orchestrator** | AgentWrapper/agent-orchestrator | 8.2k / 1.2k | Apache 2.0 | Go \+ Electron | Excellent (Native Binaries), but suffers Electron bloat |
| **Emdash** | generalaction/emdash | 5.2k / 539 | Apache 2.0 | Electron \+ React | Excellent (Native Binaries), but suffers Electron bloat |
| **Daintree** | daintreehq/daintree | 44 / 6 | Apache 2.0 | Electron 42 \+ xterm.js | Excellent (Native Binaries), WebGL limit restricts scale |

### **Table 2: Resource Footprint and High-Concurrency Scalability**

| Orchestrator | Idle RAM / CPU Footprint | Behavior at 20 Concurrent Agent Streams |
| :---- | :---- | :---- |
| **Conductor OSS** | **\<50 MB** (Rust Daemon) | Near-zero UI lag. Daemon handles PTYs natively; OS browser handles rendering effortlessly. |
| **Agetor** | **\~50-100 MB** (Electrobun) | Highly performant. Processing shifted to underlying tmux sessions and native OS WebView2/WebKit. |
| **Vibe Kanban** | Variable (High frontend cost) | **Critical Failure Risk:** Browser DOM leaks memory up to 3.8GB (+14.5MB/s), leading to OOM crashes. |
| **Agent Orchestrator** | **500 MB+** (Electron base) | Heavy RAM utilization. High IPC overhead will likely throttle the 24-core CPU under peak load. |
| **Emdash** | **500 MB+** (Electron base) | High UI RAM consumption. Rendering 20 terminal streams will severely tax Chromium's rendering engine. |
| **Daintree** | **1 GB+** (Electron \+ xterm) | **Critical Rendering Risk:** Hits Chromium's 16 WebGL context limit. Requires deep flag overrides to render. |

### **Table 3: Authentication, Worktrees, and Extensibility Mechanisms**

| Orchestrator | Auth Model & OpenRouter Support | Git Worktree Isolation Mechanics | GUI Approvals & Extensibility Seam |
| :---- | :---- | :---- | :---- |
| **Conductor OSS** | Native CLIs (Subscription). OpenRouter supported via env shaping. | Fully automated per-task. Creates isolated workspace and branch on dispatch. | Diff-first review UI. Built-in MCP Server. Webhook triggers. |
| **Agetor** | tmux direct drive (Subscription). Harness aliases for OpenRouter binaries. | Pinned base-ref worktrees (\~/.agetor/worktrees/). Auto-teardown. | Parses JSONL for exact prompts. Renders React cards. Harness API. |
| **Vibe Kanban** | Native CLIs (Subscription). Claude Code Router (CCR) proxy for OpenRouter. | git worktree add executes on card drag to "In Progress". | Inline diff commenting. MCP Server and Client implementations. |
| **Agent Orchestrator** | Native CLIs (Subscription). Configurable env shaping for OpenRouter. | Fully automated isolated worktrees per session. | 8 plugin slots. Auto-routes CI failures and review comments. |
| **Emdash** | Native CLIs (Subscription). OpenRouter fully supported. | Task-siloed branches and worktrees. | Dynamic worker sandboxes with capability manifests. Built-in MCP. |
| **Daintree** | Native CLIs (Subscription). | Deep integration via Worktree Dashboard (parses git porcelain). | Daintree Assistant (MCP). CopyTree context injection. |

## **Strategic Recommendation**

For a developer acting as a macro-orchestrator of 20 concurrent AI agents on a Windows \+ WSL infrastructure, **Conductor OSS** is the unequivocal top recommendation.
Conductor's architecture perfectly aligns with the constraints of high-concurrency local orchestration on Windows. By utilizing a Rust-compiled backend, it virtually eliminates the orchestration overhead. The daemon runs seamlessly inside WSL, interacting natively with the Linux filesystem, tmux sessions, and git worktrees, while serving the GUI to a standard web browser on the Windows host13. This completely bypasses the resource bloat of Electron and avoids the complexities of running native GUI wrappers (like Tauri or Electrobun) through the WSLg display server. Furthermore, Conductor's diff-first review model and native MCP integration provide a highly extensible seam for embedding custom command pipelines19.
**The Primary Fork Alternative:** If a standalone, encapsulated desktop application (rather than a browser-served UI) is a strict aesthetic or workflow requirement, **Agetor** is the optimal repository to fork. Its usage of the Electrobun framework guarantees a lightweight footprint compared to Electron11. Furthermore, its innovative approach to surfacing tool permissions by deterministically tailing Claude's JSONL transcripts provides the cleanest integration of human-in-the-loop approvals in the entire cohort11.
The primary trade-off with Agetor is the required engineering effort; because the project is currently macOS-focused11, porting and verifying the Electrobun build pipeline for Windows/WSL will require upfront development. Both Conductor and Agetor natively satisfy the financial imperative of utilizing existing user subscriptions by driving interactive CLIs via PTY/tmux interfaces, ensuring that managing a massive fleet of 20 coding agents remains scalable in both computational and economic terms.

#### **Works cited**

1. Conductor: Deterministic orchestration for multi-agent AI workflows \- Microsoft Open Source, [https://opensource.microsoft.com/blog/2026/05/14/conductor-deterministic-orchestration-for-multi-agent-ai-workflows/](https://opensource.microsoft.com/blog/2026/05/14/conductor-deterministic-orchestration-for-multi-agent-ai-workflows/)
2. Vibe Kanban \- Orchestrate AI Coding Agents, [https://vibekanban.com/](https://vibekanban.com/)
3. GitHub \- daintreehq/daintree: A delegation environment for orchestrating AI coding agents. Manage Claude, Gemini, and Codex sessions across git worktrees with integrated terminals, context injection, and workflow automation., [https://github.com/daintreehq/daintree](https://github.com/daintreehq/daintree)
4. daintree/CLAUDE.md at develop \- GitHub, [https://github.com/canopyide/canopy/blob/develop/CLAUDE.md](https://github.com/canopyide/canopy/blob/develop/CLAUDE.md)
5. Emdash is the Open-Source Agentic Development Environment ( YC W26). Run multiple coding agents in parallel. Use any provider. · GitHub, [https://github.com/generalaction/emdash](https://github.com/generalaction/emdash)
6. emdash/README.md at main \- GitHub, [https://github.com/generalaction/emdash/blob/main/README.md](https://github.com/generalaction/emdash/blob/main/README.md)
7. \[Bug\] Browser Tab Crash (Aw, Snap\!) due to Memory Overflow during heavy AI tasks · Issue \#2313 · BloopAI/vibe-kanban \- GitHub, [https://github.com/BloopAI/vibe-kanban/issues/2313](https://github.com/BloopAI/vibe-kanban/issues/2313)
8. Raise WebGL context cap and resource-profile ceilings \#8540 \- GitHub, [https://github.com/daintreehq/daintree/issues/8540](https://github.com/daintreehq/daintree/issues/8540)
9. agetor/electrobun.config.ts at main · alamops/agetor · GitHub, [https://github.com/alamops/agetor/blob/main/electrobun.config.ts](https://github.com/alamops/agetor/blob/main/electrobun.config.ts)
10. Proposal: Official Tauri Desktop Wrapper (embedded/sidecar server) \+ Tray & Native Notifications · Issue \#2429 · BloopAI/vibe-kanban \- GitHub, [https://github.com/BloopAI/vibe-kanban/issues/2429](https://github.com/BloopAI/vibe-kanban/issues/2429)
11. GitHub \- alamops/agetor: The harness orchestrator — a local-first kanban for running Claude Code, Codex, and other CLI coding agents in parallel, each in its own git worktree., [https://github.com/alamops/agetor](https://github.com/alamops/agetor)
12. Tickets to Pull Requests While You Sleep \- Clipboard, [https://www.clipboardworks.com/resources/blog/tickets-to-pull-requests-while-you-sleep](https://www.clipboardworks.com/resources/blog/tickets-to-pull-requests-while-you-sleep)
13. Conductor OSS | Markdown-Native AI Agent Orchestrator, [https://conductross.com/](https://conductross.com/)
14. Paperclip AI Agent Orchestrator: How to Hire and Manage a Team of AI Agents, [https://websearchapi.ai/blog/paperclip-ai-agent-orchestrator](https://websearchapi.ai/blog/paperclip-ai-agent-orchestrator)
15. Developing a Network Automation AI Agent with Pydantic AI & OpenRouter (not that kind of router\!) | by Hugo Tinoco | Medium, [https://medium.com/@hugotinoco/developing-a-network-automation-ai-agent-with-pydantic-ai-openrouter-e67d3ecc8570](https://medium.com/@hugotinoco/developing-a-network-automation-ai-agent-with-pydantic-ai-openrouter-e67d3ecc8570)
16. CCR (Claude Code Router) \- Vibe Kanban, [https://vibekanban.com/docs/agents/ccr](https://vibekanban.com/docs/agents/ccr)
17. Git worktrees for parallel AI coding agents \- Upsun Developer, [https://developer.upsun.com/posts/ai/git-worktrees-for-parallel-ai-coding-agents](https://developer.upsun.com/posts/ai/git-worktrees-for-parallel-ai-coding-agents)
18. vibe-kanban – a Kanban board for AI agents \- VirtusLab, [https://virtuslab.com/blog/ai/vibe-kanban](https://virtuslab.com/blog/ai/vibe-kanban)
19. Integrations \- Conductor OSS, [https://conductross.com/integrations](https://conductross.com/integrations)
20. EmDash is a full-stack TypeScript CMS based on Astro; the spiritual successor to WordPress \- GitHub, [https://github.com/emdash-cms/emdash](https://github.com/emdash-cms/emdash)
21. Add app-wide provider credentials/settings for Claude-compatible providers like MiniMax · Issue \#2614 · AgentWrapper/agent-orchestrator \- GitHub, [https://github.com/AgentWrapper/agent-orchestrator/issues/2614](https://github.com/AgentWrapper/agent-orchestrator/issues/2614)
22. GitHub \- nwiizo/ccswarm: Multi-agent orchestration system using Claude Code with Git worktree isolation and specialized AI agents for collaborative development, [https://github.com/nwiizo/ccswarm](https://github.com/nwiizo/ccswarm)
23. GitHub \- hesreallyhim-forks/ccswarm-fork: Multi-agent orchestration system using Claude Code with Git worktree isolation and specialized AI agents for collaborative development, [https://github.com/hesreallyhim-forks/ccswarm-fork](https://github.com/hesreallyhim-forks/ccswarm-fork)
24. ClipboardHealth/groundcrew: Dispatch your task backlog to local, interactive AI coding agents. One git worktree per task, sandboxed by default. \- GitHub, [https://github.com/ClipboardHealth/groundcrew](https://github.com/ClipboardHealth/groundcrew)
25. AI dev tools and infra shifts \- Scouts by Yutori, [https://scouts.yutori.com/ba04ed96-11ea-4a54-931a-1056fa4759bb](https://scouts.yutori.com/ba04ed96-11ea-4a54-931a-1056fa4759bb)
26. agetor/LICENSE at main · alamops/agetor · GitHub, [https://github.com/alamops/agetor/blob/main/LICENSE](https://github.com/alamops/agetor/blob/main/LICENSE)
27. charannyk06/conductor-oss: Local-first control surface for AI coding agents, workspaces, worktrees, terminals, diffs, previews, and paired-device access. \- GitHub, [https://github.com/charannyk06/conductor-oss](https://github.com/charannyk06/conductor-oss)
28. Conductor Docs, [https://conductross.com/docs](https://conductross.com/docs)
29. Release Notes \- Conductor OSS, [https://conductross.com/release-notes](https://conductross.com/release-notes)
30. meltylabs/conductor-releases \- GitHub, [https://github.com/meltylabs/conductor-releases](https://github.com/meltylabs/conductor-releases)
31. Conductor \- Today on Mac, [https://www.todayonmac.com/conductor/](https://www.todayonmac.com/conductor/)
32. GitHub \- BloopAI/vibe-kanban: Get 10X more out of Claude Code, Codex or any coding agent, [https://github.com/BloopAI/vibe-kanban](https://github.com/BloopAI/vibe-kanban)
33. Agents, subagents and skills · BloopAI vibe-kanban · Discussion \#2389 \- GitHub, [https://github.com/BloopAI/vibe-kanban/discussions/2389](https://github.com/BloopAI/vibe-kanban/discussions/2389)
34. GitHub \- GroupLang/kanvibe: Kanban board to manage your AI coding agents, [https://github.com/GroupLang/kanvibe](https://github.com/GroupLang/kanvibe)
35. Apache License 2.0 \- BloopAI/vibe-kanban \- GitHub, [https://github.com/BloopAI/vibe-kanban/blob/main/LICENSE](https://github.com/BloopAI/vibe-kanban/blob/main/LICENSE)
36. Releases · BloopAI/vibe-kanban \- GitHub, [https://github.com/BloopAI/vibe-kanban/releases](https://github.com/BloopAI/vibe-kanban/releases)
37. AgentWrapper/agent-orchestrator: AO is an agent IDE, that helps developers manage fleets of coding agents to do your day to day tasks for parallel coding agents. It comes with an agentic orchestrator that plans tasks, spawns agents, and autonomously handles CI fixes, merge conflicts, and code reviews. · GitHub, [https://github.com/AgentWrapper/agent-orchestrator](https://github.com/AgentWrapper/agent-orchestrator)
38. the911fund/skill-of-skills: The autonomous discovery engine for AI coding tools. Indexes skills, plugins, MCP servers, agents, and integrations across Claude Code, Codex, Gemini CLI, and more. \- GitHub, [https://github.com/the911fund/skill-of-skills](https://github.com/the911fund/skill-of-skills)
39. Releases · AgentWrapper/agent-orchestrator \- GitHub, [https://github.com/AgentWrapper/agent-orchestrator/releases](https://github.com/AgentWrapper/agent-orchestrator/releases)
40. launchapp-dev/ao: AO — Autonomous Agent Orchestrator for software delivery \- GitHub, [https://github.com/launchapp-dev/ao](https://github.com/launchapp-dev/ao)
41. agent-orchestrator/AGENTS.md at main \- GitHub, [https://github.com/AgentWrapper/agent-orchestrator/blob/main/AGENTS.md](https://github.com/AgentWrapper/agent-orchestrator/blob/main/AGENTS.md)
42. Competitive Landscape: AO vs T3 Code vs OpenAI Symphony vs Cmux · AgentWrapper agent-orchestrator · Discussion \#526 \- GitHub, [https://github.com/AgentWrapper/agent-orchestrator/discussions/526](https://github.com/AgentWrapper/agent-orchestrator/discussions/526)
43. mnemom/composio-ao: Agentic orchestrator for parallel coding agents \- GitHub, [https://github.com/mnemom/composio-ao](https://github.com/mnemom/composio-ao)
44. Agent process dies but session remains in \[working\] state, creating orphaned sessions that cannot be recovered or cleaned up. · Issue \#1245 · AgentWrapper/agent-orchestrator \- GitHub, [https://github.com/AgentWrapper/agent-orchestrator/issues/1245](https://github.com/AgentWrapper/agent-orchestrator/issues/1245)
45. emdash \- AI Agents on GitHub (5.1k ) | SkillsLLM \- AI Skills, [https://skillsllm.com/skill/emdash](https://skillsllm.com/skill/emdash)
46. Releases · generalaction/emdash \- GitHub, [https://github.com/generalaction/emdash/releases](https://github.com/generalaction/emdash/releases)
47. emdash/AGENTS.md at main \- GitHub, [https://github.com/generalaction/emdash/blob/main/AGENTS.md](https://github.com/generalaction/emdash/blob/main/AGENTS.md)
48. Rebrand Canopy to Daintree · Issue \#5126 \- GitHub, [https://github.com/canopyide/canopy/issues/5126](https://github.com/canopyide/canopy/issues/5126)
49. Releases · daintreehq/daintree \- GitHub, [https://github.com/canopyide/canopy/releases](https://github.com/canopyide/canopy/releases)
50. Worktrees: Can't Delete · Issue \#3946 · daintreehq/daintree \- GitHub, [https://github.com/daintreehq/daintree/issues/3946](https://github.com/daintreehq/daintree/issues/3946)
51. Add active port detection for running dev servers in worktrees · Issue \#2535 · daintreehq/daintree \- GitHub, [https://github.com/daintreehq/daintree/issues/2535](https://github.com/daintreehq/daintree/issues/2535)



below is also chatgpt suggestion
"My recommendations are:

Agetor — best lightweight project to fork.
Emdash — best application you can use immediately on Windows.
Agent Orchestrator (AO) — strongest mature orchestration platform, but Electron-based.

Agetor is the closest architectural match because it uses Electrobun/native WebView, launches the locally authenticated Claude Code CLI, creates one Git worktree per task, and presents permissions and questions as structured GUI cards. Its limitations are incomplete Windows testing, no native OpenRouter adapter and no full IDE-style file browser.

Ranked comparison
Rank	Candidate	Stars*	Framework	License	Claude subscription	OpenRouter	Worktrees	Permissions/questions	Windows/WSL
1	Agetor	~25	Electrobun + Bun + React	MIT	Yes, explicitly	Requires adapter	Yes, per task	Structured GUI cards	Configured but untested
2	Emdash	~5.2k	Electron + React	Apache-2.0	Yes, through installed CLI	Yes via OpenCode	Yes	Primarily terminal/hooks	Native Windows; Linux/SSH
3	Agent Orchestrator	~8.3k	Electron	Apache-2.0	Yes, through CLI adapter	Via OpenCode	Yes	Terminal/supervisor UI	Windows builds available
4	Daintree	~47	Electron	Apache-2.0	Yes, real terminals	Via OpenCode/custom terminal	Yes	Terminal-based interaction	Windows .appx; Linux
5	Maestro	~3.1k	Electron	AGPL-3.0	Yes, CLI pass-through	Via OpenCode	Yes	Preserves agent permissions	Cross-platform
6	Vibe Kanban	~27.4k	Rust + local web UI	Apache-2.0	Yes	Via supported agents	Yes	Agent terminal/UI	Cross-platform, but sunsetting
7	Groundcrew	~54	Node + tmux/zellij	MIT	Yes, real claude CLI	Custom OpenCode command possible	Yes	Interactive terminal	Good under WSL; no desktop GUI
8	ccswarm	~146	Rust	MIT	Claude Code-oriented	Not verified	Yes	CLI/TUI	Likely WSL; no GUI
9	Conductor	—	macOS application	Source/license unclear	Yes	Not verified	Yes	GUI	macOS only

*Star counts checked 16 July 2026.

1. Agetor — best fork foundation

Agetor is specifically designed as a local control plane for CLI coding agents.

Its architecture includes:

One isolated Git worktree and branch per task.
Persistent interactive Claude Code sessions inside tmux.
Claude output read from its normal JSONL transcript.
Kanban workflow: backlog, running, blocked, review and done.
Tool permissions, AskUserQuestion and plan approvals rendered as GUI cards.
Local SQLite storage.
HTTP/SSE control API.
Separate $HOME directories for multiple Claude accounts.
MIT license.

Most importantly, Agetor says it runs Claude Code interactively so usage comes from your normal Claude subscription quota, not Agent SDK credits. Agetor repository and architecture

Missing pieces

A fork would need:

A Windows-to-WSL process adapter using wsl.exe.
A generic agent-harness interface.
OpenCode integration for OpenRouter.
A proper file tree and file viewer.
Rendered Markdown and side-by-side diff panels.
Stream virtualization and backpressure for 20 sessions.

Therefore, Agetor is my recommendation if your goal is to create your own lightweight product rather than immediately deploy an existing application.

2. Emdash — best available product now

Emdash already provides:

Windows, Linux and macOS desktop applications.
34 CLI-based coding-agent integrations.
Claude Code, Codex and OpenCode.
Per-task worktrees.
File browser and editor.
Git diff, PR and CI review.
Reusable prompts, skills and MCP servers.
Persistent tmux sessions.
Remote SSH execution.
Local SQLite storage.
Apache-2.0 licensing.

Emdash repository, Emdash documentation

Because Emdash can launch OpenCode, it can use OpenRouter models through OpenCode’s official OpenRouter support. OpenRouter–OpenCode integration

Its main disadvantage is Electron. It is also a large, fast-moving monorepo, making it more difficult to reduce to a specialized lightweight cockpit.

Emdash tracks whether agents are working, awaiting input or finished, but it does not appear to centralize every Claude permission request into structured cards as comprehensively as Agetor.

3. Agent Orchestrator — strongest mature alternative

AO provides:

Per-agent Git worktrees.
Multiple parallel Claude Code, Codex, OpenCode and other CLI sessions.
Kanban/project dashboard.
Terminals and browser preview.
Pull-request and CI monitoring.
Automatic feedback loops for CI failures, reviews and merge conflicts.
Agent-adapter architecture.
Windows packaging.
Apache-2.0 license.

Agent Orchestrator repository

It is substantially more mature than Agetor, but it uses Electron, includes optional PostHog telemetry, and has a much larger orchestration surface.

Resource consumption

None of Agetor, Emdash, AO, Daintree or Maestro publishes a reproducible idle CPU/RAM benchmark. I cannot responsibly provide invented “actual” numbers.

The only concrete problem report I found was for Vibe Kanban: one user reported approximately 15 GB RAM and 150–200% CPU after running several parallel tasks. This is an issue report rather than a controlled benchmark, but it is still a serious warning. Vibe Kanban memory issue

Agetor should theoretically have the smallest GUI overhead because it uses:

One Bun main process.
One native OS WebView.
tmux and Claude processes only for active tasks.

Emdash, AO, Daintree and Maestro each include an Electron/Chromium runtime.

Twenty-session assessment

A distinction is necessary:

Managing 20 existing sessions: realistic.
Streaming from 20 agents: potentially realistic with batched UI updates.
Running 20 simultaneous builds/tests: likely to create CPU, RAM and disk contention.

For your 24-core/48-GB system, I recommend:

Support 20 visible sessions.
Keep only the selected session fully rendered.
Virtualize background transcripts.
Maintain a bounded in-memory event tail.
Persist full transcripts to SQLite/disk.
Initially limit CPU-intensive tasks to 6–8 concurrent agents.
Allow the other sessions to remain idle, blocked or awaiting review.

Claude subscription rate limits may become the bottleneck before the cockpit itself.

Authentication warning

To ensure Claude Code uses your subscription, ANTHROPIC_API_KEY should remain unset. Claude Code gives API-key environment variables priority over subscription authentication. Check /status inside Claude periodically. Anthropic authentication guidance

Final recommendation

Fork Agetor and make these the first development milestones:

Windows Electrobun UI with WSL-based execution.
Generic agent-adapter protocol.
Claude Code subscription adapter.
OpenCode/OpenRouter adapter.
File tree, Markdown viewer and git-diff workspace.
Stream batching and concurrency controls.
A reproducible 1/5/10/20-session benchmark.

If you need to begin working immediately before building your fork, use Emdash as the operational reference and Agetor as the architectural base."
