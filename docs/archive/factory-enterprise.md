# Enterprise with Droids

> How to deploy, secure, and operate Droids in the world’s highest‑security environments.

Factory’s enterprise platform is designed for the **highest‑security customers**—systemically important banks, governments, healthcare, national security, and other regulated organizations.

Instead of forcing you into a single cloud IDE, Droid is a **CLI and agent runtime that runs anywhere**:

* On developer laptops, in any terminal or IDE
* In CI/CD pipelines (GitHub, GitLab, internal runners)
* In VMs, Kubernetes clusters, and hardened devcontainers
* In **fully airgapped environments** with no outbound internet access

This section explains how to deploy Droid safely, govern which models and tools it can use, and observe its behavior at enterprise scale.

***

## What this section covers

Use these pages together as your enterprise playbook for Droids:

<CardGroup cols={2}>
  <Card title="Identity & Access" icon="user-shield">
    How orgs, projects, folders, and users are identified; how SSO/SCIM and RBAC determine who can run Droid and with which permissions.
    See [Identity & Access Management](/enterprise/identity-and-access).
  </Card>

  <Card title="Privacy & Data Flows" icon="shield-check">
    Exact data flows for code, prompts, and telemetry across cloud, hybrid, and fully airgapped deployments.
    See [Privacy, Data Flows & Governance](/enterprise/privacy-and-data-flows).
  </Card>

  <Card title="Network & Deployment" icon="server">
    Reference architectures for cloud‑managed, hybrid, and fully airgapped deployments, plus proxy and mTLS configuration.
    See [Network & Deployment Configuration](/enterprise/network-and-deployment).
  </Card>

  <Card title="LLM Safety & Controls" icon="shield-alert">
    How Droid classifies command risk, enforces allow/deny lists, uses Droid Shield for secret scanning, and integrates hooks and sandboxes.
    See [LLM Safety & Agent Controls](/enterprise/llm-safety-and-agent-controls).
  </Card>

  <Card title="Models & Integrations" icon="boxes">
    Hierarchical model allow/deny, LLM gateways, BYOK, MCP servers, droids, commands, and how Droid plugs into your existing AI stack.
    See [Models, LLM Gateways & Integrations](/enterprise/models-llm-gateways-and-integrations).
  </Card>

  <Card title="Analytics & Compliance" icon="file-badge">
    OTEL‑native telemetry, analytics, audit logging, and how Factory supports SOC2, ISO 27001, ISO 42001 and internal regulatory reviews.
    See [Usage, Cost & Productivity Analytics](/enterprise/usage-cost-and-analytics) and [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring).
  </Card>
</CardGroup>

***

## Enterprise foundations

### Multi‑deployment by design

Factory supports three deployment patterns for Droid, all built on the same core binary and configuration model:

1. **Cloud‑managed** – Droid runs on developer machines and CI but uses Factory’s cloud for coordination and optional analytics. Models are either Factory‑brokered or brought by you.
2. **Hybrid enterprise** – Droid runs entirely in your infrastructure (VMs, CI runners, containers), optionally connecting to Factory cloud for UX while all LLMs and telemetry terminate inside your network.
3. **Fully airgapped** – Droid runs in a network with **no outbound internet access**. Models and OTEL collectors are hosted entirely inside this environment; Factory never receives traffic.

You can start in cloud‑managed mode, then migrate critical workloads to hybrid or airgapped environments without changing how developers talk to Droid.

### Hierarchical control, not per‑device drift

Enterprise policy is expressed through a **hierarchical settings model**:

* **Org** → global defaults and hard security policies
* **Project** → repo‑level settings committed to `.factory/`
* **Folder** → narrower team or subsystem overrides inside a repo
* **User** → personal preferences only where higher levels are silent

Higher levels **cannot be overridden** by lower ones. Org and project settings extend downward; users can opt into stricter controls but never weaken them. This hierarchy governs models, tools, MCP servers, droids, commands, autonomy levels, and telemetry destinations.

Learn more in [Hierarchical Settings & Org Control](/enterprise/hierarchical-settings-and-org-control).

### Defense‑in‑depth agent safety

LLMs are probabilistic; Factory treats them as powerful but untrusted components. Droid’s safety story combines:

* **Deterministic controls** – command risk classification, allow/deny lists, file and repo protections, and sandbox boundaries
* **Droid Shield** – secret scanning and DLP‑style checks across prompts, files, and commands
* **Hooks** – programmable enforcement points (pre‑prompt, pre‑tool, pre‑command, pre‑git, post‑edit) to integrate with your own security systems
* **Sandboxed runtimes** – running Droid inside devcontainers and hardened VMs for high‑risk work

These layers are independent of which LLM or IDE a developer prefers.

### OTEL‑native observability

All serious enterprise deployments need to answer: *“What are agents doing, where, and at what cost?”*

Droid emits **OpenTelemetry metrics, traces, and logs** so you can:

* Send telemetry directly to existing collectors (Prometheus, Datadog, Splunk, Jaeger, etc.)
* Track sessions, LLM usage, code edits, tool invocations, and errors per org/team/user
* Correlate Droid activity with SDLC metrics you already use

Factory’s own cloud analytics are **optional**; high‑security customers can route all telemetry exclusively to their own infrastructure.

See [Usage, Cost & Productivity Analytics](/enterprise/usage-cost-and-analytics) and [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring).

***

## Trust & compliance

Factory maintains a security and compliance posture suitable for the most demanding organizations:

* **SOC 2**
* **ISO 27001**
* **ISO 42001**

You can find the latest reports, sub‑processor lists, and security architecture details in our **Trust Center**.

For a deeper dive into how Droid fits your regulatory and audit requirements, start with [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring).


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Network & Deployment Configuration

> Reference architectures and network requirements for cloud, hybrid, and fully airgapped Droid deployments.

Droids are designed to run anywhere: on laptops, in CI pipelines, on VMs and Kubernetes clusters, and in fully airgapped environments.

This page describes the **supported deployment patterns**, their **network requirements**, and how to combine Droid with proxies, custom CAs, mTLS, and sandboxed containers.

***

## Deployment patterns

Factory supports three canonical patterns. You can mix patterns across teams and environments.

### 1. Cloud‑managed deployment

In this pattern, Droid runs on developer machines and build infrastructure, while **Factory cloud** provides orchestration and optional analytics.

<CardGroup cols={2}>
  <Card title="Where Droid runs" icon="terminal">
    * Developer laptops and workstations
    * CI/CD runners (GitHub, GitLab, internal)
    * Optional devcontainers or remote development environments
  </Card>

  <Card title="What lives in Factory cloud" icon="cloud">
    * Control plane and org metadata
    * Optional usage analytics dashboards
    * Authentication and access control for the web UI
  </Card>
</CardGroup>

LLM traffic can still be routed through **your own gateways and providers**; Factory does not need to broker model access.

Cloud‑managed deployments are ideal for organizations that allow well‑scoped cloud usage but want strong governance over models, keys, and telemetry.

### 2. Hybrid enterprise deployment

In hybrid deployments, Droid runs entirely within your infrastructure, while you may still use Factory cloud selectively for user experience and coordination.

* Droid processes run on **your VMs, containers, CI runners, and remote dev environments**.
* LLM traffic goes through **your LLM gateways or cloud providers** under your accounts.
* OTEL telemetry is sent to **your collectors and observability stack**.
* Factory cloud may see limited metadata (for example, org and project identifiers) if you enable cloud features.

This pattern is common for large enterprises and critical infrastructure where **network segmentation** and **central governance** are mandatory.

### 3. Fully airgapped deployment

In fully airgapped deployments:

* Droid runs in an isolated network with **no outbound internet connectivity**.
* Models are served from **on‑prem or in‑network endpoints**.
* OTEL collectors and observability tooling are hosted entirely inside the airgap.
* Factory cloud is not reachable at runtime; any artifacts (binaries, configuration) are imported via offline processes.

This is the default pattern for national security, defense, and other highly classified workloads.

***

## Network requirements

Network requirements vary per pattern.

### Cloud‑managed

In addition to your model providers and OTEL collector endpoints, Droid typically needs:

* Access to Factory cloud endpoints (for example, `*.factory.ai` and related domains).
* Outbound access to any configured LLM providers or LLM gateways.
* Outbound access to OTEL collectors if they are hosted outside the local network.

Your security team can tighten access by:

* Restricting outbound hosts to the minimum set of domains.
* Using HTTPS proxies and custom CAs as described below.
* Routing all LLM traffic through a central gateway and monitoring.

### Hybrid

In hybrid mode, Droid generally needs only:

* Access to your **internal LLM gateways and model endpoints**.
* Access to your **internal OTEL collectors and SIEM/observability stack**.
* Optional, tightly scoped access to Factory cloud endpoints for specific features.

You can run Droid within private subnets, VPNs, and Kubernetes clusters, inheriting all existing firewall and network controls.

### Fully airgapped

In fully airgapped environments:

* Droid traffic is entirely **contained inside your network**.
* No external domains are required at runtime.
* Updates to Droid and configuration bundles are handled through your own artifact repositories or offline processes.

***

## Proxies, custom CAs, and mTLS

Enterprise networks frequently require HTTP(S) proxies, organization‑specific certificate authorities, and mutual TLS.

### HTTP(S) proxy support

Droid respects standard proxy environment variables:

```bash  theme={null}
export HTTPS_PROXY="https://proxy.example.com:8080"
export HTTP_PROXY="http://proxy.example.com:8080"

# Bypass proxy for specific hosts
export NO_PROXY="localhost,127.0.0.1,internal.example.com,.corp.example.com"
```

Use these to route traffic from Droid to LLM gateways and any Factory cloud endpoints through your corporate proxy.

### Custom certificate authorities

If your organization uses custom CAs for HTTPS inspection or internal endpoints, configure the runtime environment so Droid trusts those CAs (for example, via `NODE_EXTRA_CA_CERTS` or OS‑level trust stores).

### Mutual TLS (mTLS)

For environments that require client certificates when calling gateways or internal APIs, configure your containers, VMs, or runners with the appropriate certificate, key, and passphrase. These settings are usually handled at the HTTP client or proxy layer that Droid uses.

***

## Running in secure containers and VMs

Running Droid inside hardened containers and VMs is one of the most effective ways to **bound the blast radius** of any agent mistakes or misconfigurations.

Recommended patterns include:

* **Devcontainers for untrusted code**
  * Use locked‑down devcontainers with restricted filesystem mounts and outbound network rules.
  * Run Droid with higher autonomy only inside these containers, never directly on the host.

* **Isolated VMs for sensitive operations**
  * Create dedicated VMs for production‑adjacent work (for example, migration tooling).
  * Use OS policies to restrict which repos, secrets, and networks those VMs can access.

* **CI/CD pipelines**
  * Run Droid in ephemeral CI jobs with short‑lived credentials and minimal privileges.
  * Combine with hooks and Droid Shield to prevent leaks and enforce approval workflows.

See [LLM Safety & Agent Controls](/enterprise/llm-safety-and-agent-controls) for how autonomy, allow/deny lists, and Droid Shield interact with these environments.

***

## Configuration surfaces

Network and deployment configuration is expressed through:

* **Environment variables** – proxies, gateways, OTEL endpoints, custom certificates.
* **Org and project `.factory/settings.json`** – hierarchical policies about where Droid may run, which models and gateways are allowed, and default telemetry destinations.
* **Org config endpoints** – for large organizations, a central configuration service can distribute a standard `.factory` bundle to all environments.

For details on the hierarchy and merge behavior, see [Hierarchical Settings & Org Control](/enterprise/hierarchical-settings-and-org-control).


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Models, LLM Gateways & Integrations

> How Droids connect to your models, LLM gateways, MCP servers, droids, commands, and existing engineering tools.

Factory is designed to plug into the **AI and developer tooling you already use**. This page explains how to control which models Droid can use, how to route traffic through LLM gateways, and how to manage MCP servers, droids, commands, and platform integrations.

***

## Model management and hierarchy

Model access is governed by the same hierarchical settings system used throughout Factory:

* **Org level**
  * Defines the **authoritative list of allowed models** and categories.
  * Can explicitly ban models (for example, non‑enterprise APIs) so they cannot be re‑enabled by projects or users.
  * Decides whether user‑supplied BYOK keys are allowed at all.

* **Project level**
  * Can **add additional models** on top of the org‑approved set (for example, project‑specific fine‑tunes) but cannot re‑enable banned ones.
  * Can set project defaults—for example, “use a small model for tests, a large model for refactors.”

* **User level**
  * Can choose personal defaults **within the allowed set**.
  * Cannot see or select models that higher levels have disallowed.

Because the hierarchy is extension‑only, upgrades and policy changes at the org level flow consistently across all environments.

***

## LLM gateways

Many enterprises centralize model access behind an **LLM gateway** that handles authentication, routing, and policy enforcement.

Factory works with gateways in two ways:

1. **Directly configured gateway endpoints**
   * `.factory/settings.json` can specify gateway base URLs for specific providers.
   * Environment variables can route calls (for example, `ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`).
   * Custom models configured via [BYOK](/cli/configuration/byok) can point to gateway endpoints using `base_url` and provider‑specific settings, so the same gateway policy applies whether models are built‑in or custom.

2. **Org‑level gateway policy**
   * Org admins can require that all model traffic go through specific gateways.
   * BYOK can be restricted so that only centrally managed keys and identities are used.

When you use a gateway, **data handling and retention policies are those of the gateway and underlying providers**; Droid simply uses the endpoints and credentials you configure.

For concrete examples of configuring custom models (including gateway‑backed models), see [Custom models & BYOK](/cli/configuration/byok), which covers the `customModels` array in `~/.factory/settings.json` and how those models appear in the `/model` selector.

***

## Cloud providers and BYOK

Factory supports multiple model deployment patterns:

* **Direct cloud providers** – calling OpenAI, Anthropic, Google, and others using your enterprise credentials.
* **Cloud AI platforms** – AWS Bedrock, GCP Vertex, Azure OpenAI, using IAM‑backed authentication.
* **On‑prem / self‑hosted models** – models running inside your network, exposed via approved gateways.

Bring‑your‑own‑key (BYOK) is controlled by policy:

* Org admins can allow or block **user‑supplied API keys**.
* Even when BYOK is allowed, orgs can restrict which providers and endpoints keys may target.
* Project configs can define shared keys or credentials for team‑wide models in secure stores.

In high‑security environments, orgs often:

* Disable user BYOK entirely.
* Route all traffic through gateways that enforce data residency and audit logging.

***

## MCP servers

The **Model Context Protocol (MCP)** lets Droid access external systems—ticket queues, documentation, databases, and more—through well‑defined tools.

MCP servers can be very powerful; they may read from internal systems or perform side‑effecting actions. Factory gives you several levers to control them:

* **Org allowlist/blocklist**
  * Org admins define which MCP servers are allowed at all.
  * Servers not on the allowlist are ignored, even if a project tries to configure them.

* **Project‑level configuration**
  * Projects can enable subsets of the allowed servers and configure environment variables and connection details.

* **User‑level opt‑in**
  * Users can enable or disable MCP servers from the allowed set for their own sessions.

These controls let you safely expose internal systems to Droid while ensuring each server has passed security and compliance review.

***

## Droids, commands, and tools

Factory’s ecosystem of **droids, commands, and hooks** is also governed hierarchically.

### Org‑level droids and commands

* Org admins can publish **blessed droids** and **shared commands** into an org‑level `.factory` bundle.
* These often encode security‑reviewed workflows such as:
  * `/security-review`
  * `/migrate-service`
  * `/refactor-module`
* Projects and users can use these resources but cannot modify them.

### Project‑level extensions

* Projects add **specialized droids and commands** in their own `.factory/droids/` and `.factory/commands/` directories.
* These extend org resources with project‑specific logic—such as knowledge of particular services, schemas, or runbooks.

### User‑level customization

* Users can add personal droids and commands in `~/.factory/droids/` and `~/.factory/commands/`.
* These are useful for individual workflows but must still respect org and project policies (for example, cannot call disallowed tools or models).

Hooks tie everything together by providing enforcement and logging at the edges of these tools. See [LLM Safety & Agent Controls](/enterprise/llm-safety-and-agent-controls) for more.

***

## Integration environments

Because Droid is CLI‑first, it integrates with many environments without forcing developers into a particular IDE.

Common patterns include:

* **Terminals and shells**
  * Direct use of Droid in `bash`, `zsh`, `fish`, or Windows shells.
  * Shell aliases and scripts to standardize workflows across teams.

* **IDE and editor integrations**
  * Integrations with IDEs such as VS Code, JetBrains tools, and others that treat Droid as a backend agent.
  * Policies and telemetry still flow through the same hierarchical settings and OTEL pipelines.

* **CI/CD pipelines**
  * Running Droid in GitHub Actions, GitLab CI, or internal pipelines for tasks like code review, refactoring, and migration.
  * Use separate identities and credentials for CI compared to developers.

* **Remote and locked-down environments**
  * Running Droid in air-gapped or restricted environments.
  * Supporting desktop and browser-based interfaces for secure enterprise deployments.

Across all of these, the same enterprise controls apply: **models, tools, MCP servers, and telemetry are constrained by org and project policy, not by the IDE or environment**.


---

# Identity & Access Management

> How Droids use org, project, and user identity to control who can run agents, where, and with which permissions.

Identity and access management controls **who can run Droid**, in which environments, and under what policies.

This page provides an overview of the identity model, roles, and environments; detailed SSO and SCIM setup instructions live in [SSO, IdP & SCIM Provisioning](/enterprise/identity-sso-and-scim).

***

## Identity model

Every Droid run is associated with three dimensions of identity:

<CardGroup cols={2}>
  <Card title="User or machine identity" icon="user">
    Human developers authenticate via SSO (SAML/OIDC), inheriting their
    directory groups and roles. Automation (CI/CD, scheduled jobs) runs under
    **machine identities** with long‑lived tokens or workload identities.
  </Card>

  <Card title="Org / project / folder" icon="folders">
    The active repo and `.factory/` folders determine the **org, project, and
    folder context**. Policies at these levels decide which models, tools, and
    integrations Droid may use.
  </Card>

  <Card title="Runtime environment" icon="server">
    Whether Droid is running on a laptop, in a CI runner, or in a sandboxed
    VM/devcontainer is captured as environment attributes. Policies can treat
    these differently (for example, higher autonomy only in CI or sandboxes).
  </Card>

  <Card title="Session metadata" icon="activity">
    Each Droid session records metadata such as session ID, CLI version, and git
    branch, which is available for audit and OTEL telemetry.
  </Card>
</CardGroup>

***

## Org identity and SSO (overview)

Most enterprises integrate Factory with an identity provider (IdP) such as **Okta, Azure AD, or Google Workspace**.

At a high level:

* **Org membership** is derived from IdP groups mapped to Factory organizations and teams.
* **SSO sign‑in** gives developers access to both the web platform and Droid using corporate credentials.
* **Role information** (for example, `Owner`, `Admin`, `User`) flows from IdP groups into Factory roles.

For step‑by‑step SSO and SCIM configuration—including setting up the IdP application, mapping attributes, and enabling provisioning—see [SSO, IdP & SCIM Provisioning](/enterprise/identity-sso-and-scim).

***

## Role‑based access control (RBAC)

Factory distinguishes between three broad classes of actors:

* **Org administrators**

  * Define org‑level `.factory` configuration, including model policies, global command allow/deny lists, and default telemetry targets.
  * Decide which deployment patterns (cloud, hybrid, airgapped) are supported and where Droid binaries may run.
  * Configure security features such as maximum autonomy level and whether user‑supplied BYOK keys are allowed.

* **Project owners / maintainers**

  * Own project‑level `.factory/` folders that live in version control.
  * Provide team‑specific models, droids, commands, and hooks that extend org policy without weakening it.
  * Configure project‑specific policies, for example limiting Droid to certain repositories or directories.

* **Developers**
  * Customize personal preferences in `~/.factory/` (for example, default model choice within the allowed set).
  * Run Droid locally, in IDEs, or via team‑provided scripts and CI jobs.
  * Cannot override any setting defined at org or project level.

Role assignment flows from your IdP into Factory; the **hierarchical settings engine** enforces what each role can effectively change. See [Hierarchical Settings & Org Control](/enterprise/hierarchical-settings-and-org-control) for the exact precedence rules.

***

## Devices, environments, and workspace trust

Because Droid is a CLI, it can run in many environments:

* Developer laptops (macOS, Linux, Windows)
* Remote dev servers or workspaces
* CI runners and build agents
* Hardened VMs and devcontainers

Enterprise customers typically combine Droid with **endpoint management** and **workspace trust** controls:

<AccordionGroup>
  <Accordion title="Endpoint & MDM controls">
    Use tools like **Jamf, Intune, or other MDM solutions** to control where Droid binaries can be installed, which users can run them, and which configuration files they can read.

    Common patterns include:

    * Only allowing Droid to run under managed user accounts.
    * Restricting configuration directories to corporate‑managed volumes.
    * Enforcing OS‑level disk encryption and screen lock policies.
  </Accordion>

  <Accordion title="Workspace trust">
    Treat Droid as trusted only in **known repositories and environments**:

    * Pin Droid to specific paths or repos on developer machines.
    * Require elevated approval or sandboxed environments for untrusted code.
    * Use project‑level `.factory/` folders to mark which repos are "Droid‑ready" and what policies should apply.
  </Accordion>

  <Accordion title="Environment‑aware policies">
    The same developer may run Droid in multiple contexts: on their laptop, in CI, or in an isolated container.

    Policies can take these differences into account:

    * Allow higher autonomy or more powerful tools **only** inside devcontainers or CI runners.
    * Restrict network access or command execution when running on laptops.
    * Tag OTEL telemetry with environment attributes to support environment‑specific alerting.
  </Accordion>
</AccordionGroup>

***

## How identity flows into policy and telemetry

Identity and environment information are used in two main ways:

1. **Policy evaluation** – hierarchical settings (org → project → folder → user) use identity to determine which configuration bundle applies to a given run.
2. **Telemetry and audit** – Droid emits OTEL metrics, traces, and logs with attributes like `user.id`, `team.id`, `session.id`, and environment tags so you can build per‑org and per‑team dashboards.

For details on how these identities are encoded in telemetry, see [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring).


---

# Privacy, Data Flows & Governance

> How code, prompts, and telemetry move in cloud, hybrid, and fully airgapped Droid deployments, and how to control those flows.

High‑security organizations need precise answers to **what data goes where, when, and under whose control**.

Factory’s answer is simple: **data boundaries are determined by the models, gateways, and deployment pattern you choose**, and Droid is configurable to respect those boundaries.

***

## Overview: three main data flows

When you run Droid, there are three primary ways data can move:

1. **Code and files** – local reads and writes on your filesystem and git repositories.
2. **LLM traffic** – prompts and context sent to model providers or LLM gateways.
3. **Telemetry** – metrics, traces, and logs emitted via OpenTelemetry.

How far each flow travels depends on whether you are in a **cloud‑managed**, **hybrid**, or **fully airgapped** deployment.

<CardGroup cols={3}>
  <Card title="Cloud‑managed" icon="cloud">
    Droid runs on laptops and CI, talking to Factory’s cloud for orchestration
    and (optionally) analytics. LLM requests go to your chosen model providers
    or LLM gateways.
  </Card>

  <Card title="Hybrid" icon="cloud-off">
    Droid runs entirely inside your infra. LLM and OTEL traffic terminate in
    your network; Factory cloud may only see minimal metadata if you enable it.
  </Card>

  <Card title="Fully airgapped" icon="shield">
    Droid, models, and collectors all live inside an isolated network. No
    runtime dependency on Factory cloud; **no traffic leaves the environment**.
  </Card>
</CardGroup>

***

## Code and file access

Droid is a filesystem‑native agent:

* It reads your code, configuration, and test files **directly from the local filesystem** at the moment they’re needed.
* It uses LLMs to analyze existing code and generate new code, then applies patches on disk, with git as the source of truth where available.
* It does **not** upload or index your codebase into a remote datastore; there is no static or “cold” copy of your repository stored in Factory cloud.

In all deployment patterns:

* The **agent loop and runtime execute entirely on the machine** where Droid runs (developer workstation, CI runner, VM, or container).
* File contents can be included in LLM requests as context, so the data path for code always follows the same LLM request pipeline described below.
* **File reads and writes remain local** to that environment; only the portions you choose to include in prompts leave the machine, and only to the model endpoints you configure.
* Hooks and Droid Shield run locally inside that agent loop. By default they behave like local SAST / policy checks; they only send data off the machine if you explicitly configure a hook to call an external service.

You control which files and directories Droid can see through standard OS permissions and your repository layout. See [LLM Safety & Agent Controls](/enterprise/llm-safety-and-agent-controls) for additional file‑level protections.

***

## LLM requests and model‑specific guarantees

When Droid needs model output, it sends prompts and context to **your configured models and LLM gateways**.

By default, Droid can target **enterprise‑grade endpoints** for providers like Azure OpenAI, AWS Bedrock, Google Vertex AI, OpenAI, Anthropic, and Gemini, using contracts that support zero data retention and enterprise privacy controls. In these configurations, Factory routes traffic **directly** to the provider’s official APIs; we do not proxy this traffic through third‑party services or store prompts and responses in Factory cloud.

If you instead configure your own endpoints—LLM gateways, self‑hosted models, or generic HTTP APIs—the privacy guarantees are entirely determined by those systems and your agreements with them; Factory does not add additional protections on top.

### Model and gateway options

* **Cloud model providers** – OpenAI, Anthropic, Google, and others via their enterprise offerings.
* **Cloud AI platforms** – AWS Bedrock, GCP Vertex, Azure OpenAI, using your cloud accounts.
* **On‑prem / self‑hosted models** – models served inside your network or airgapped environment via HTTP/gRPC gateways.
* **LLM gateways** – central gateways that normalize traffic, add authentication, enforce rate limits, and log usage.

### How Droid interacts with models

* Org and project policies decide **which models and gateways are allowed**, and whether users can bring their own keys.
* In high‑security settings, orgs commonly:
  * Prefer direct enterprise endpoints (for example, Azure OpenAI, AWS Bedrock, Google Vertex AI, OpenAI Enterprise, Anthropic/Claude Enterprise, Gemini Enterprise) to get first‑party zero‑retention guarantees.
  * Disable ad‑hoc user‑supplied keys and generic internet endpoints.
  * Treat any LLM gateways or self‑hosted models as in‑scope security systems, subject to the same reviews and monitoring as other critical services.

See [Models, LLM Gateways & Integrations](/enterprise/models-llm-gateways-and-integrations) for configuration details.

***

## Telemetry and analytics

Telemetry is how you understand *what* Droid is doing and *where*. Factory treats OpenTelemetry as the primary interface for this.

### OTEL as the source of truth

* Droid emits **OTLP signals** (metrics, traces, logs) to the endpoints you configure via environment variables or `.factory` settings.
* Typical destinations include OTEL collectors feeding **Prometheus, Datadog, New Relic, Splunk, Loki, Jaeger, Tempo**, and similar systems.
* High‑security customers commonly deploy OTEL collectors **inside their own networks** and never send telemetry to Factory.

### Optional Factory cloud analytics

In cloud‑managed deployments, you can opt into Factory’s own analytics dashboards, which may:

* Aggregate anonymized usage metrics to show adoption, model usage, and cost trends.
* Surface per‑org and per‑team insights for platform and leadership teams.

These analytics are optional; org administrators decide whether to enable them.

For more on signals and schema, see [Usage, Cost & Productivity Analytics](/enterprise/usage-cost-and-analytics) and [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring).

***

## Data retention and residency

### Factory‑hosted components

In cloud‑managed mode, Factory may store limited operational logs and metrics for:

* Authentication and administrative actions (for example, org configuration changes).
* Service health and debugging.

Retention and residency for these logs are documented in the Trust Center and can be tuned per customer engagement.

### Customer‑hosted components

For hybrid and airgapped deployments:

* **LLM traffic** is handled entirely by your providers and gateways; Factory does not see it.
* **Telemetry** is stored in your observability stack; retention is governed by your own policies.
* **Code, configuration, and secrets** never leave your environment unless you explicitly send them to external services via hooks or gateways.

In fully airgapped environments, Factory never receives any runtime data; you are responsible for all retention and residency decisions.

***

## Governance controls in practice

To make these guarantees enforceable rather than aspirational, Factory exposes **governance levers** at the org and project levels:

* Model and gateway allow/deny lists.
* Policies for whether user‑supplied BYOK keys are allowed.
* Global and project‑specific hooks for DLP, redaction, and approval workflows.
* OTEL endpoint configuration (including requiring on‑prem collectors).
* Maximum autonomy level and other safety controls, especially in less‑trusted environments.

These levers are implemented through the **hierarchical settings** system described in [Hierarchical Settings & Org Control](/enterprise/hierarchical-settings-and-org-control).


---

# LLM Safety & Agent Controls

> How Droids classify risk, enforce allow/deny policies, use Droid Shield, and integrate hooks and sandboxes to keep agents safe.

Factory treats LLMs as powerful but untrusted components. Droid’s safety model combines **deterministic controls, programmable hooks, and sandboxed runtimes** so that even frontier models can operate safely in high‑security environments.

***

## Two layers of safety

We differentiate between:

1. **Deterministic controls** – hard boundaries that do not depend on model behavior.
2. **LLM steering** – prompts and context that guide models toward better behavior without providing guarantees.

Enterprise security should be built primarily on deterministic controls; steering is a quality‑of‑life improvement.

<CardGroup cols={2}>
  <Card title="Deterministic controls" icon="shield-check">
    * Command risk classification
    * Global and project‑level allow/deny lists
    * File and repo protection
    * Droid Shield secret scanning
    * Hooks for enforcement and logging
    * Sandboxed VMs and containers
  </Card>

  <Card title="LLM steering" icon="sparkles">
    * Project and org‑level rules and instructions
    * Standardized commands and workflows
    * Context selection and enrichment via MCP
    * Model choice and reasoning effort defaults
  </Card>
</CardGroup>

***

## Command risk classification

Every shell command Droid proposes is classified into a **risk level** based on patterns and context (for example, file deletion, network access, package installation, database access).

Typical levels include:

* **Low risk** – read‑only commands and local diagnostics (for example, `ls`, `cat`, `git status`).
* **Medium risk** – commands that modify code or install dependencies (for example, `npm install`, `go test ./...`).
* **High risk** – commands that delete data, change system configuration, or interact with sensitive resources (for example, `rm -rf`, `kubectl delete`, `psql` against production).

Org and project policies can map risk levels to behavior, such as:

* Always allow low‑risk commands.
* Require user approval for medium‑risk commands.
* Block high‑risk commands entirely or only allow them in specific environments (for example, isolated devcontainers).

Risk information is also emitted via OTEL so security teams can monitor how often high‑risk commands are proposed or attempted.

***

## Command allowlists and denylists

Admins can define **global and project‑specific allow/deny lists** in hierarchical settings:

* **Deny lists** – patterns for commands that are never permitted (for example, `rm -rf`, `sudo *`, `curl *://sensitive-endpoint`).
* **Allow lists** – specific commands or patterns that can run without additional approval in certain environments.

Because settings are extension‑only:

* Org‑level denies and allows **cannot be removed** by projects or users.
* Projects can add additional allows or denies within their repos.
* Users cannot weaken the policy; they can only choose stricter personal defaults.

This keeps command policy consistent across thousands of machines while still allowing local specialization.

***

## Droid Shield: secret scanning and DLP

**Droid Shield** adds a dedicated layer of protection for secrets and sensitive content.

When enabled, Droid Shield can:

* Scan **files** before they are read or edited.
* Scan **prompts** before they are sent to models.
* Scan **commands** before they are executed.

It detects patterns such as:

* API tokens and access keys.
* Passwords and database connection strings.
* Private keys and certificates.
* Organization‑specific identifiers (configurable patterns).

Based on policy, Droid Shield can:

* Block the operation entirely.
* Redact the sensitive portions before continuing.
* Emit OTEL events and logs for security review.
* Call out to a **customer DLP service** via hooks for deeper analysis.

Org admins configure Droid Shield at the org and project levels; users cannot disable it where it is enforced.

***

## Hooks for enforcement and logging

Hooks are Droid’s **programmable safety and observability interface**. They allow you to run your own code at key points in the agent loop.

Common hook points include:

* **Before prompt submission** – inspect prompts for secrets, PII, or policy violations.
* **Before file reads or writes** – block or redact access to sensitive files.
* **Before command execution** – enforce approval workflows or block dangerous commands.
* **Before git operations** – prevent unauthorized `git push` or interactions with restricted branches.
* **After code generation or edits** – run linters, security scanners, or internal compliance checks.

Typical enterprise use cases:

<AccordionGroup>
  <Accordion title="Block direct git pushes">
    Require all code changes to flow through your existing tooling by blocking `git push` in Droid sessions and instructing developers to use internal CL/PR tooling instead.
  </Accordion>

  <Accordion title="Integrate with DLP and CASB systems">
    Forward prompts and file snippets to your DLP or CASB APIs before they reach LLMs; deny or redact operations that violate policy.
  </Accordion>

  <Accordion title="Enforce environment‑specific policies">
    Allow certain tools and commands only in CI or sandboxed environments, based on environment tags emitted by Droid.
  </Accordion>
</AccordionGroup>

See [Hooks Guide](/cli/configuration/hooks-guide) and [Hooks Reference](/reference/hooks-reference) for implementation details and examples.

***

## Sandboxing with containers and VMs

Running Droid in **sandboxed devcontainers and VMs** lets you safely grant more autonomy where it is useful, without exposing production systems.

Recommended patterns:

* Use Docker/Podman devcontainers with restricted filesystem mounts and network egress.
* Run Droid with higher autonomy only inside containers or VMs that **do not have direct access to production databases or secrets**.
* Use separate credentials and environment variables for sandboxed versus production‑adjacent environments.

In OTEL telemetry, you can tag sessions by environment (for example, `environment.type=local|ci|sandbox`) to build environment‑specific dashboards and alerts.

***

## Steering models toward safe behavior

While deterministic controls are the foundation, **LLM steering** improves quality and reduces how often dangerous actions are even proposed.

Org and project settings can define:

* **Rules and instructions** – security guidelines, coding standards, and organization‑specific instructions that apply to every request.
* **Standardized commands and workflows** – shared commands (for example, `/security-review`, `/migrate-service`) that bake in safe patterns.
* **Context enrichment** – MCP servers that expose documentation, runbooks, and internal APIs so models have accurate information instead of guessing.

Because these are instructions, not enforcement, they complement rather than replace the hard boundaries described above.


---

# Hierarchical Settings & Org Control

> How org, project, folder, and user settings combine to control models, tools, safety policies, and telemetry for Droid.

Factory’s enterprise story is built on a **single, predictable settings hierarchy**. Instead of ad‑hoc per‑machine configuration, orgs express policy once and have it apply consistently across laptops, CI, VMs, and airgapped environments.

This page explains how the hierarchy works and how to use it to govern models, tools, safety policies, and telemetry.

***

## The four levels

Settings are defined in `.factory/` folders with a consistent structure at four levels:

```text  theme={null}
Org         → Central `.factory/` bundle (or config endpoint)
Project     → <git-root>/.factory/
Folder      → <git-root>/.../subfolder/.factory/
User        → ~/.factory/
```

Each `.factory/` folder can contain:

* `settings.json` – general settings (models, safety, preferences, telemetry).
* `mcp.json` – MCP server configurations.
* `droids/` – droid definitions.
* `commands/` – custom commands.
* `hooks/` – hook definitions.

The **same schema** applies at every level. What changes is **precedence**.

***

## Extension‑only semantics

Factory uses **extension‑only** semantics instead of traditional “override” behavior.

* Higher levels (org, project) **cannot be overridden** by lower levels.
* Lower levels (folder, user) can only **add** to what higher levels define when those fields are unset.
* This ensures org policies remain intact even as projects and users customize their experience.

There are three merge modes depending on the data type.

### 1. Simple values – first wins

For simple scalar values (strings, numbers, booleans):

* The first level that sets a value “wins.”
* Lower levels cannot change or remove that value.

Examples:

* `sessionDefaults.model`
* `sessionDefaults.autonomyLevel`
* `maxAutonomyLevel`

This guarantees that org decisions (such as which models or autonomy levels are allowed) remain authoritative.

### 2. Arrays – union, cannot remove

Array fields accumulate across levels:

* Org entries are always present and **cannot be removed**.
* Project and folder levels can add more entries.
* User level can add more entries but cannot remove or weaken higher‑level entries.

Examples:

* Command **allow lists** and **deny lists**.
* Lists of enabled hooks or features.

This pattern is ideal for policies like “these commands are always denied” or “these hooks are always enabled,” while still allowing teams to extend the list.

### 3. Objects – keys are locked per level

For object fields:

* Keys defined at a higher level are **locked**; their contents cannot be changed by lower levels.
* Lower levels can add new keys but not modify or delete existing ones.

Examples:

* `customModels` – org defines `claude-enterprise`; projects can add `payments-gpt`, users can add `personal-experimental`, but none can change or remove `claude-enterprise`.
* MCP server definitions – org defines which servers exist and how they connect; projects decide which to use.

This keeps critical configuration (like model endpoints and MCP servers) under centralized control.

***

## Org configuration

Large organizations typically manage an **org‑level `.factory` bundle** or config endpoint that:

* Specifies allowed models, gateways, and BYOK policies.
* Defines global command allow/deny lists.
* Sets defaults for autonomy, reasoning effort, and safety features like Droid Shield.
* Configures OTEL defaults (endpoints, sampling, and attributes).
* Publishes org‑standard droids, commands, and hooks.

This bundle is distributed to all environments where Droid runs—developer machines, CI, VMs, and airgapped clusters.

Org policy is the foundation; projects and users build on top of it.

***

## Project and folder configuration

Projects and folders use `.factory/` directories checked into version control to specialize org policy for particular codebases and teams.

Common responsibilities include:

* Adding project‑specific models and gateways within the allowed set.
* Defining project‑specific droids (for example, `/migrate-service`, `/refactor-module`).
* Configuring hooks that know about the project’s tests, linters, and deployment processes.
* Tightening safety controls for high‑risk repositories.

Folder‑level `.factory/` directories are useful in monorepos where different subsystems have different policies.

***

## User configuration

Developers can configure `~/.factory/` for **personal preferences only** where higher levels are silent.

Examples:

* Choosing a preferred model from the allowed set.
* Setting default behavior for display options and minor UX preferences.
* Enabling additional hooks or tools that do not conflict with org policy.

Because of extension‑only semantics, users cannot:

* Re‑enable models or tools that org or project settings have disallowed.
* Loosen command allow/deny lists.
* Reduce autonomy or safety requirements set by org or project.

***

## Example: enforcing a model policy

Suppose your org wants to:

* Allow only approved enterprise models.
* Disallow user‑supplied API keys.
* Force all prompts through a particular LLM gateway.

You would:

1. Define the allowed models and gateway endpoints in the org `.factory/settings.json`.
2. Set a policy flag to disable user BYOK entirely.
3. Configure hooks to verify that any model selection or endpoint use matches the org‑approved set.

Projects and users can still choose **which of the approved models** to use for different tasks, but cannot break these guarantees.

***

## Example: environment‑specific autonomy

Consider an org that wants to:

* Allow high autonomy in CI and sandboxed containers.
* Limit autonomy on developer laptops.

You could:

1. At org level, set `maxAutonomyLevel` to `high`.
2. In project settings, define environment‑aware hooks that:
   * Inspect environment tags (for example, `environment.type=local|ci|sandbox`).
   * Downgrade or block autonomy levels above `medium` when running on laptops.
3. Optionally, define stricter folder‑level policies for particularly sensitive repos.

Again, users cannot override these rules; they can only choose safer personal defaults within the allowed space.

***

## Putting it all together

The hierarchical settings system underpins everything described in the other enterprise pages:

* [Identity & Access Management](/enterprise/identity-and-access) – who can change which level of settings.
* [Privacy, Data Flows & Governance](/enterprise/privacy-and-data-flows) – where data and telemetry are allowed to go.
* [Network & Deployment Configuration](/enterprise/network-and-deployment) – which environments Droid can run in and how it connects.
* [LLM Safety & Agent Controls](/enterprise/llm-safety-and-agent-controls) – policies for commands, tools, and Droid Shield.
* [Models, LLM Gateways & Integrations](/enterprise/models-llm-gateways-and-integrations) – control over models, gateways, MCP servers, droids, and commands.
* [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring) – guarantees and telemetry used to prove compliance.

By expressing policy once at the right level, you can run Droid across cloud, hybrid, and airgapped environments **without per‑machine drift or one‑off configuration**.


---

# Compliance, Audit & Monitoring

> How Droids support SOC2, ISO 27001/42001, regulatory reviews, and continuous monitoring using OpenTelemetry and audit logs.

Security and compliance teams need clear answers to **who did what, when, where, and with which data**. This page explains how Droids fit into your compliance posture and how to integrate them with your existing monitoring and audit infrastructure.

***

## Certifications and Trust Center

Factory maintains an enterprise‑grade security and compliance program, including:

* **SOC 2**
* **ISO 27001**
* **ISO 42001**

Our **Trust Center** provides up‑to‑date reports, security architecture documentation, and sub‑processor lists. Use it as the primary reference for security and compliance reviews.

***

## Audit trails and events

There are two complementary sources of audit information:

1. **Factory‑side audit logs** (for cloud‑managed features).
2. **Customer‑side OTEL telemetry** emitted by Droid.

### Factory‑side audit logs (cloud‑managed)

When you use Factory’s hosted services, the control plane records key events such as:

* Authentication events and SSO/SCIM changes.
* Org and project configuration updates.
* Policy changes (model allow/deny lists, autonomy limits, Droid Shield settings, hooks configuration).
* Administrative actions in the web UI.

These logs can be exported via the Trust Center or integrations agreed upon in your enterprise engagement.

### Customer‑side OTEL telemetry

Droid emits OTEL metrics, traces, and logs that can serve as **fine‑grained audit data** inside your own systems, including:

* Session start and end events, tagged with user, team, environment, and project information.
* Tool usage events (which tools were invoked, how long they ran, and whether they succeeded).
* Command execution metadata, including risk classification and outcome.
* Code modification events (which files and repositories were changed).

You control how long these signals are retained and how they are correlated with other systems such as CI/CD pipelines, SIEMs, and case management tools.

***

## OpenTelemetry schema and collectors

Factory’s OTEL support is designed to integrate with existing observability tooling.

At a high level, telemetry includes:

* **Resource attributes** – describing the environment, service, org, team, and user.
* **Metrics** – counters and histograms for sessions, LLM usage, tools, and errors.
* **Traces and spans** – describing the lifecycle of sessions and automated runs.
* **Logs** – structured events for key actions and errors.

You can deploy OTEL collectors that:

* Receive OTLP data from Droid.
* Enrich or redact attributes based on your own policies.
* Forward telemetry to multiple destinations (for example, Prometheus + Loki, Datadog, Splunk, or S3).

This architecture keeps **ownership of telemetry firmly in your hands**, even when using Factory’s cloud‑managed features.

For more details on the metrics and traces useful for cost and productivity analysis, see [Usage, Cost & Productivity Analytics](/enterprise/usage-cost-and-analytics).

***

## Regulatory and industry use cases

Factory is designed to support organizations operating under strict regulatory regimes. While implementation details differ, common patterns include:

<AccordionGroup>
  <Accordion title="Financial services">
    * Use hybrid or airgapped deployments for systems subject to strict data residency and record‑keeping requirements.
    * Route all LLM traffic through gateways that implement your bank’s data policies.
    * Use OTEL telemetry and hooks to ensure Droid activity is visible in your SIEM and aligned with your control framework.
  </Accordion>

  <Accordion title="Healthcare and PHI">
    * Deploy Droid in environments that never expose protected health information to external LLMs.
    * Use model allowlists that include only providers and gateways that meet your PHI handling requirements.
    * Use Droid Shield and DLP hooks to prevent PHI from being included in prompts or logs.
  </Accordion>

  <Accordion title="National security and defense">
    * Rely on fully airgapped deployments with on‑prem models and collectors.
    * Treat Droid as an internal tool whose artifacts and logs never leave your network.
    * Use OTEL and hooks to integrate with mission‑specific monitoring and incident response tooling.
  </Accordion>
</AccordionGroup>

***

## Deployment and configuration for compliance teams

To integrate Droid into your compliance and monitoring stack:

1. **Decide on deployment pattern** – cloud‑managed, hybrid, or fully airgapped.
2. **Define model and gateway policies** – which providers and gateways are allowed, and where.
3. **Configure OTEL collectors and destinations** – ensure all Droid telemetry flows into your SIEM and observability tools.
4. **Set up hooks and Droid Shield** – enforce DLP, approval workflows, and environment‑specific controls.
5. **Document policies and mappings** – connect Droid controls to your internal control framework and regulatory obligations.

Most of this configuration is expressed via the hierarchical settings system described in [Hierarchical Settings & Org Control](/enterprise/hierarchical-settings-and-org-control).


---

# GitHub Integration Security

> Security architecture, data flows, and controls for the Factory Droid GitHub Action integration.

The Factory Droid GitHub Action enables automated code review and PR assistance directly within your GitHub workflows. This page explains the security architecture, data flows, and controls that govern how the integration operates.

***

## Overview

The Droid GitHub Action (`Factory-AI/droid-action`) runs **entirely inside GitHub Actions** using your own runners. It does not require a separate hosted service or persistent connection to Factory infrastructure beyond standard API authentication.

<CardGroup cols={2}>
  <Card title="Runs in your environment" icon="server">
    The action executes on GitHub‑hosted or self‑hosted runners you control. No
    external compute resources are provisioned.
  </Card>

  <Card title="No persistent code storage" icon="database">
    Code is checked out transiently for the workflow run and discarded
    afterward. Factory does not store your source code.
  </Card>

  <Card title="Scoped permissions" icon="shield-check">
    The action requests only the GitHub permissions it needs and tokens are
    automatically revoked after each run.
  </Card>

  <Card title="Standard Factory authentication" icon="key">
    Uses your Factory API key, subject to your org's existing model allowlists,
    rate limits, and policies.
  </Card>
</CardGroup>

***

## Architecture and data flows

When a workflow runs, the following sequence occurs:

1. **Trigger detection** – The action detects `@droid` mentions in PR comments, descriptions, or review comments.
2. **Permission verification** – Before executing, the action verifies the triggering user has write access to the repository.
3. **Context gathering** – Droid collects PR metadata, changed files, and existing comments from the checked‑out repository.
4. **Droid Exec** – The CLI runs with GitHub MCP tools pre‑registered, allowing it to interact with the PR via GitHub APIs.
5. **LLM requests** – Prompts are sent to your configured model providers through Factory's standard routing.
6. **Results** – Droid posts inline comments or updates the PR description directly via GitHub APIs.
7. **Token revocation** – GitHub App tokens are automatically revoked at the end of the workflow.

### Data boundaries

| Data type           | Where it flows                     | Retention                                |
| ------------------- | ---------------------------------- | ---------------------------------------- |
| Source code         | GitHub runner (transient checkout) | Discarded after workflow                 |
| PR metadata         | GitHub APIs                        | GitHub's retention policies              |
| Prompts and context | Configured LLM providers           | Per your model provider agreements       |
| Workflow logs       | GitHub Actions                     | Your repository's log retention settings |
| Debug artifacts     | GitHub Actions artifacts           | 7 days (configurable)                    |

***

## Authentication and authorization

### Factory API key

The action requires a Factory API key (`FACTORY_API_KEY`) stored as a GitHub secret. This key:

* Authenticates Droid Exec sessions with Factory's API.
* Is subject to your org's model allowlists, rate limits, and policies.
* Should be rotated regularly following your organization's key management practices.

<Warning>
  Never commit API keys directly to your repository. Always use GitHub Actions
  secrets.
</Warning>

### GitHub App tokens

When using the Factory Droid GitHub App:

* The app requests an installation token scoped to the specific repository.
* Tokens are short‑lived and automatically revoked after the workflow completes.
* The app only requests permissions necessary for its operation (contents, pull requests, issues).

If you prefer not to use the GitHub App, you can provide a custom `github_token` input with appropriate permissions.

### User permission verification

Before executing any `@droid` command, the action verifies:

1. The triggering user has **write access** to the repository.
2. The user is not a bot (unless explicitly allowed via `allowed_bots` input).
3. The comment or trigger matches the expected format.

This prevents unauthorized users from invoking Droid.

***

## Security controls

### Permission scoping

The action requests only the GitHub permissions it needs:

```yaml  theme={null}
permissions:
  contents: write # Read code, write for fixes
  pull-requests: write # Comment on and update PRs
  issues: write # Comment on issues
  id-token: write # OIDC token for secure auth
  actions: read # Read workflow run metadata
```

You can further restrict permissions in your workflow file based on your security requirements.

### Bot and user filtering

Control who can trigger the action:

| Input                     | Purpose                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------- |
| `allowed_bots`            | Comma‑separated list of bot usernames allowed to trigger, or `*` for all. Default: none. |
| `allowed_non_write_users` | Usernames to allow without write permissions. Use with extreme caution.                  |

### Network restrictions (experimental)

For enhanced security, you can restrict network access during Droid execution:

```yaml  theme={null}
- uses: Factory-AI/droid-action@v1
  with:
    factory_api_key: ${{ secrets.FACTORY_API_KEY }}
    experimental_allowed_domains: |
      api.factory.ai
      api.anthropic.com
      api.openai.com
```

This limits outbound connections to only the specified domains.

### Secrets protection

The action follows security best practices for secrets handling:

* API keys are passed via environment variables from GitHub secrets.
* The `show_full_output` option is disabled by default to prevent accidental exposure of sensitive data in logs.
* Debug artifacts are retained for only 7 days by default.

<Warning>
  Enabling `show_full_output` may expose sensitive information in publicly
  visible workflow logs. Only enable for debugging in non‑sensitive
  environments.
</Warning>

***

## Audit and monitoring

### Workflow logs

All Droid activity is logged in GitHub Actions workflow runs, providing:

* Timestamps for all operations.
* Command inputs and outputs (unless containing sensitive data).
* Success/failure status for each step.
* Links to any comments or changes made.

### Debug artifacts

The action uploads debug artifacts including:

* Droid session logs.
* Console output.
* Session metadata.

These artifacts are retained for 7 days by default and can be used for troubleshooting or audit purposes.

### Integration with Factory telemetry

If your organization uses Factory's OTEL telemetry, Droid Exec sessions from GitHub Actions are included in your telemetry data, providing:

* Session metrics tagged with repository and workflow context.
* LLM usage and cost attribution.
* Tool invocation tracking.

See [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring) for details on Factory's telemetry capabilities.

***

## Deployment recommendations

<AccordionGroup>
  <Accordion title="For security‑conscious organizations">
    1. **Use repository secrets** – Store `FACTORY_API_KEY` as a repository or organization secret.
    2. **Review workflow permissions** – Ensure the workflow file requests only necessary permissions.
    3. **Restrict bot access** – Keep `allowed_bots` empty unless you have a specific need.
    4. **Enable branch protection** – Require PR reviews before merging Droid‑assisted changes.
    5. **Monitor workflow runs** – Review Droid activity in your GitHub Actions logs regularly.
    6. **Consider network restrictions** – Use `experimental_allowed_domains` to limit network access.
  </Accordion>

  <Accordion title="For regulated environments">
    * **Self‑hosted runners** – Run the action on self‑hosted runners in your controlled environment.
    * **Model allowlists** – Configure Factory org policies to restrict which models Droid can use.
    * **Audit retention** – Adjust artifact retention periods to meet your compliance requirements.
    * **Integrate with SIEM** – Export GitHub Actions logs and Factory telemetry to your security monitoring tools.
  </Accordion>
</AccordionGroup>

***

## Comparison with other deployment patterns

| Aspect                | GitHub Action       | CLI on developer machine  | Droid Exec in CI            |
| --------------------- | ------------------- | ------------------------- | --------------------------- |
| Execution environment | GitHub runners      | Local workstation         | Your CI runners             |
| Code access           | Transient checkout  | Full local access         | Transient checkout          |
| Authentication        | Factory API key     | Factory API key           | Factory API key             |
| Trigger               | PR events, comments | Manual invocation         | CI pipeline events          |
| Audit trail           | GitHub Actions logs | Local + Factory telemetry | CI logs + Factory telemetry |

All deployment patterns use the same underlying Droid Exec runtime and are subject to the same Factory org policies.


---

# Usage, Cost & Productivity Analytics

> How to measure Droid adoption, control LLM spend, and understand impact using OpenTelemetry and optional Factory dashboards.

Enterprise adoption requires more than a good developer experience—you need to understand **who is using Droid, on what, and at what cost**.

Factory is built around **OpenTelemetry (OTEL)** so you can plug Droid directly into your existing observability stack, with optional cloud analytics for organizations that want a hosted view.

***

## OTEL‑native metrics and traces

Droid emits OTEL signals that capture how it is used across your org.

### Key metric families

Examples of metric categories include:

* **Session metrics**
  * Counts of interactive and headless sessions.
  * Session duration and active engagement time.

* **LLM usage metrics**
  * Tokens in/out per model and provider.
  * Request counts and latencies.
  * Error rates and retry behavior.

* **Tool usage metrics**
  * Tool invocations and execution time.
  * Success/failure rates.
  * Command risk levels proposed and executed.

* **Code modification metrics**
  * Files and lines modified, created, or deleted.
  * Distribution across repositories and teams.

### Traces and spans

Traces can show the lifecycle of a session or automation run:

* Session start → prompt construction → LLM call → tool execution → code edits → validation.
* Spans capture timing and metadata for each step, including model choice, tools invoked, and error conditions.

These signals allow you to build dashboards in systems like **Prometheus, Grafana, Datadog, New Relic, or Splunk** without depending on a proprietary analytics service.

For a deeper look at the telemetry schema and how it supports compliance and audits, see [Compliance, Audit & Monitoring](/enterprise/compliance-audit-and-monitoring).

***

## Factory cloud analytics (optional)

In cloud‑managed deployments, Factory can provide a **hosted analytics view** for platform and leadership teams.

Typical views include:

* Adoption metrics by org, team, and repository.
* Model usage and performance trends.
* High‑level cost estimates for LLM usage.
* Top workflows and droids by frequency.

These dashboards are built on top of the same signals Droid emits via OTEL; enabling them does not change the underlying telemetry model.

Hybrid and fully airgapped deployments commonly rely solely on **customer‑owned OTEL pipelines** and disable hosted analytics entirely.

***

## Cost management strategies

LLM cost control is a combination of **model policy**, **usage patterns**, and **observability**.

Recommended practices:

<AccordionGroup>
  <Accordion title="Constrain the model catalog">
    Use org‑level policies to limit which models are available.

    * Prefer smaller models for everyday tasks; reserve large models for complicated refactors or design work.
    * Disable experimental or high‑cost models by default.
    * Enforce model choices per environment (for example, cheaper models in CI).
  </Accordion>

  <Accordion title="Tune autonomy and context usage">
    Higher autonomy and larger context windows consume more tokens.

    * Set reasonable defaults for autonomy level and reasoning effort.
    * Use hooks to cap context size or block unnecessary large prompts.
    * Encourage teams to iterate with tighter scopes (for example, specific directories instead of entire monorepos).
  </Accordion>

  <Accordion title="Use OTEL for cost monitoring">
    Feed token and request metrics into your observability stack.

    * Build per‑team and per‑model dashboards.
    * Alert on unusual spikes in usage.
    * Compare cost curves before and after policy changes.
  </Accordion>
</AccordionGroup>

***

## Measuring productivity impact

Cost only matters in the context of outcomes. With OTEL, you can correlate Droid usage with **software delivery and quality metrics** you already track.

Common approaches:

* Link OTEL traces for Droid sessions with CI builds, test runs, and deployment pipelines.
* Measure how often Droid is involved in changes that reduce incidents, resolve alerts, or improve test coverage.
* Use code modification metrics to estimate automation impact (for example, lines of code refactored or migrated).

These analyses are done entirely in your existing observability and analytics stack; Factory’s role is to provide clean, structured signals from Droid.


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt
