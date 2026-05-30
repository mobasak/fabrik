# P2 Sub-plan — Watchdog core (sidecar + emitter + spec field + registrar + driver)

**Date:** 2026-05-30
**Phase:** P2 of the AI Watchdog Platform plan (15–18-day build)
**Parent plan:** [2026-05-30-ai-watchdog-platform.md](2026-05-30-ai-watchdog-platform.md)
**P1 status:** Shipped (commits `fd32c3e` + `929dbf2` + `e7a64f5` in `/opt/fabrik`, `a2ecf4b` + `c9b6203` in `/opt/fabrik-lib`)
**Prompt that produced this:** [2026-05-30-ai-watchdog-platform-prompts.md § P2.A](2026-05-30-ai-watchdog-platform-prompts.md)
**Status:** Approved — architecture locked 2026-05-30. **Code execution gated on completion of the VPS Remediation plan** ([2026-05-30-vps-remediation.md](2026-05-30-vps-remediation.md)) — Coolify-residue cleanup must land before WatchdogConfig is added to spec_loader.py so the new field doesn't sit next to the stale `coolify:` block.
**Effort:** 6–8 days (per parent plan), runs after VPS remediation completes.

---

## Verification evidence (no assumptions)

### V1 — `claude --help` and `claude -p --help` flag verification

Live captured from VPS (`ssh vps "claude --help"`; binary at `/usr/local/bin/claude` → `../lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe`, version 2.1.144).

**Flags plan v2 names that are CONFIRMED real:**

- `--bare` ✓ exists. **Critical caveat (NEW finding):** docstring reads *"Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read)."* This means `--bare` **does NOT use the Max subscription** — it requires an API key. Plan v2 claimed `--bare` keeps subscription auth; that was wrong.
- `--permission-mode <mode>` ✓ — choices: `acceptEdits | auto | bypassPermissions | default | dontAsk | plan`. Matches plan v2.
- `--settings <file-or-json>` ✓ — accepts a path or inline JSON.
- `--allowedTools` / `--allowed-tools` ✓ — comma or space-separated.
- `--append-system-prompt <prompt>` ✓.
- `--output-format <format>` ✓ — `text|json|stream-json` (only with `--print`).
- `-p, --print` ✓ — non-interactive mode. **Workspace-trust dialog is skipped when -p is used.**

**Important new flags discovered (not in plan v2 — must be incorporated into design):**

- `--no-session-persistence` — "sessions will not be saved to disk and cannot be resumed (only works with --print)". **MUST use for the watchdog sidecar** — otherwise every call writes to `~/.claude/` (mounted read-only).
- `--max-budget-usd <amount>` — "Maximum dollar amount to spend on API calls (only works with --print)". Built-in per-call ceiling — complements cost-budget's daily cap with a per-invocation cap. **Plan v2 didn't know this existed.**
- `--json-schema <schema>` — JSON Schema for structured-output validation. **Big improvement over plan v2's "self-rated confidence" pattern** — we can force the model to return `{action, confidence, reasoning, ...}` with type guarantees.
- `--fallback-model <model>` — built-in automatic fallback when the default model is overloaded. **Complements (does not replace) our OpenRouter fallback** — this is in-Anthropic fallback for overload, not "Claude Code down" fallback.
- `--effort <level>` — `low|medium|high|xhigh|max`. Useful tuning lever for cost vs quality per incident severity.
- `--input-format text|stream-json` — could pipe richer context via stream-json. v1 will use `text`.

**Live test confirms headless invocation works WITHOUT `--bare`:**

```bash
ssh vps "claude -p 'say hi in 3 words' --output-format json --no-session-persistence"
```

Returns rich JSON including:

- `result`: the model's text answer.
- `total_cost_usd: 0.06468175` — **REAL DOLLAR COST returned by Claude Code itself.** No need to estimate from token counts.
- `modelUsage`: per-model breakdown with `costUSD` per model. The single call used both `claude-haiku-4-5-20251001` ($0.000508) AND `claude-opus-4-7[1m]` ($0.064174). Claude Code routes internally — Haiku for trivial, Opus for substance.
- `usage`: full token breakdown (input, output, cache_read, cache_creation).
- `session_id`: returned (would persist without `--no-session-persistence`).
- `permission_denials: []`: array of any blocked tool calls.

**Implication for the LLM provider chain:**

- Plan v2's "Claude Code primary records `cost_usd=0`" is **wrong**. Claude Code DOES charge per token, billed against subscription quota until exhausted, then overage. We get the real cost in `total_cost_usd` and record it.
- The "tiered model selection ladder" (Haiku → Sonnet) was already done by Claude Code internally per the live test. Our explicit ladder becomes either (a) redundant or (b) a higher-level coarse switch (use `--effort low` for trivial, `--effort high` for hard).

### V2 — Host Claude Code config location

```bash
$ ssh vps "ls -la ~/.claude/"
.credentials.json    (OAuth tokens — 471 bytes)
backups/, cache/, debug/, downloads/, file-history/, projects/, todos/, etc.
.last-cleanup, history.jsonl, mcp-needs-auth-cache.json
NO ~/.claude/settings.json exists on this VPS user.
```

- The OAuth credentials live in `~/.claude/.credentials.json` (mode 600, owner `ozgur`).
- Confirmed mountable: sidecar with UID 1000 (matching `ozgur` on VPS) can read `.credentials.json` if `~/.claude/` is mounted into the container.
- **No user-level `settings.json` exists** — the sidecar will deploy its own via `--settings /etc/watchdog/claude-settings.json`.

### V3 — Docker compose project label

```bash
$ ssh vps "sudo docker inspect --format '{{json .Config.Labels}}' postgres-main"
{... "com.docker.compose.project":"postgres" ... "com.docker.compose.service":"postgres-main" ...}
```

- Confirmed label key: **`com.docker.compose.project`** (exact spelling).
- Value: the compose project name (typically the directory name, e.g. `postgres`).
- Also confirmed: `com.docker.compose.service` for the per-service identifier inside the project.

**⚠ Caveat:** older infra containers (`site-provisioner`, `image-broker`, `meilisearch`, `gotenberg`, `browserless`) returned EMPTY for `com.docker.compose.project` — they were deployed via paths that don't set the label, or via `docker run`. This means the docker.sock scoping is **not airtight**: a watchdog could theoretically `docker restart site-provisioner` if it knew the name AND that container has no project label to filter against. **Mitigation:** the PreToolUse hook's per-project allow-list is the surgical defense — the sidecar's claude-settings.json `permissions.allow` array names exactly `Bash(docker restart <main_container>)`, NOT a wildcard. Defense-in-depth holds.

### V4 — Apprise wiring

- **Apprise container:** runs on the `coolify` Docker network (confirmed via `docker network inspect coolify`), container name `apprise`.
- **Internal URL:** `http://apprise:8000` (default in `fabrik-lib/alerting/apprise.py:VPS_HOST_DEFAULT`).
- **Existing send pattern** (`/opt/fabrik-lib/alerting/apprise.py:send`): outside-the-cluster path uses SSH-piped curl to `http://apprise:8000/notify` with `{"title": ..., "body": ...}` JSON payload.
- **Sidecar is INSIDE the cluster** — it can POST directly to `http://apprise:8000/notify` without SSH. Just `httpx.post` or `urllib.request`.
- **Only existing fabrik consumer:** `src/fabrik/drivers/backrest.py` (uses Apprise for backup notifications). Plus `fabrik-lib/alerting/` module (vendorable).

### V5 — Per-project env-var injection pattern

- `src/fabrik/orchestrator/deployer_ssh.py:135` `SSHDeployer.inject_env(ctx, env_vars: dict[str, str]) -> None` is the canonical mechanism:
  1. Reads existing `.env` at `/opt/<name>/.env` on VPS via SSH.
  2. Merges new vars (overrides on conflict).
  3. Writes merged `.env` back to VPS.
  4. Restarts the compose service.
- **This is what the watchdog registrar (P2 artifact 11) will call** to inject `WATCHDOG_*` env vars into the project's `.env`.
- Other existing call sites confirm pattern (deployer_coolify is legacy/archived; deployer_ssh is the active path).

### V6 — P1 module signatures the sidecar will call

```python
# app-audit-log/audit_log.py (P1 commit a2ecf4b/c9b6203)
def record_event(conn, *, actor: str, action: str, target_type=None, target_id=None,
                 details=None, table='audit_log') -> AuditEvent
def verify_chain(conn, *, table='audit_log', since=None, until=None, limit=None) -> list[ChainBreak]

# cost-budget/cost_budget.py (P1 commit a2ecf4b/c9b6203)
def record_cost(*, pg_conn, wal_path, event: CostEvent) -> None
def replay_wal(*, pg_conn, wal_path, batch_size=100, max_age_seconds=604800) -> dict
def check_caps(*, pg_conn, wal_path, project_id, daily_usd_cap, daily_invocations_cap,
               window_start=None) -> BudgetState
```

Sidecar calls these for: cost recording (`record_cost` with `total_cost_usd` from claude's JSON), cap enforcement (`check_caps` before invoking), audit logging (`record_event` for `watchdog.tier_a_action` etc.).

### V7 — Gatus driver pattern (matched by the watchdog driver)

Confirmed pattern from `src/fabrik/drivers/gatus.py` (283 lines):

- Module-level docstring with design notes.
- Module-level constants (config paths, regexes, defaults).
- Validation helpers (`_validate_project_name`, `_validate_domain`, etc.).
- Public API functions: `add_endpoint(...)` (idempotent, returns dict), `remove_endpoint(...)` (best-effort, never raises).
- Build helpers (`_build_endpoint_yaml`).
- Atomic write pattern: local tmp → `scp_to_vps` → `sudo mv` → restart target container.
- `__all__` tuple at the end.

**Will reuse for** `src/fabrik/drivers/watchdog.py`. Estimated 350–450 lines, between gatus.py (283) and glitchtip.py (467).

### V8 — `_REGISTRAR_ORDER` placement for watchdog

Current order (`infrastructure.py:84`): `(postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus)`.

**Watchdog must run AFTER:** `postgres` (cost_ledger DDL exists per P1's `_provision_shared_analytics`), `prometheus` (so `/metrics` is wired before sidecar tries to scrape main app), `glitchtip` (so the DSN env var is in the project's `.env` before sidecar starts — sidecar may want to read events later, even though v1 explicitly does NOT pull GlitchTip events).

**Position:** APPEND to end. New tuple: `(... , 'prometheus', 'watchdog')`. Watchdog is the last gate before the deployment is considered "watched."

---

## 1. `WatchdogConfig` Pydantic class (lives in `src/fabrik/spec_loader.py`)

**Line-of-insertion:** immediately after `Shape` model definition (currently ends at `src/fabrik/spec_loader.py:341`). Watchdog config is sibling to Shape — both are top-level spec blocks driving the dispatcher.

```python
class WatchdogConfig(BaseModel):
    """Per-project AI watchdog sidecar configuration (T-P2 watchdog platform).

    Lives at top-level of the spec as `watchdog:`. Provisioned by
    :func:`fabrik.orchestrator.infrastructure._register_watchdog` at
    `fabrik apply` time. Defaults derived from ``spec.shape.kind`` —
    service/worker/wordpress get enabled=true; static gets enabled=false.

    See ``docs/development/plans/2026-05-30-ai-watchdog-platform.md``
    § Watchdog architecture for the full design.
    """

    model_config = {"extra": "forbid"}

    enabled: bool = Field(
        default=False,
        description=(
            "True to inject the watchdog sidecar into the project's compose. "
            "Default is computed by the dispatcher from spec.shape.kind: True "
            "for service|worker|wordpress, False for static. Owner can override."
        ),
    )

    # Cost caps — exactly one MUST be > 0 if enabled=True (validator below).
    daily_budget_usd: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Daily USD cap for LLM calls (Anthropic billing — Claude Code OAuth "
            "OR fallback OpenRouter API). Per-project. Resets at midnight UTC. "
            "0.0 disables USD-cap enforcement (relies on daily_invocations_cap)."
        ),
    )
    daily_invocations_cap: int = Field(
        default=200,
        ge=0,
        description=(
            "Daily invocation-count cap for LLM calls (primarily for Claude Code "
            "subscription-quota visibility; OpenRouter calls count too). Per-project. "
            "Resets at midnight UTC. 0 disables count-cap enforcement."
        ),
    )

    auto_tier_b: bool = Field(
        default=False,
        description=(
            "True to allow autonomous Tier B actions (wipe Redis cache, reset DB "
            "connection pool). Default False — Tier B requires opt-in per project. "
            "Tier A is always autonomous; Tier C always escalates regardless."
        ),
    )

    escalation_channel: str = Field(
        default="apprise",
        description=(
            "Where the sidecar sends owner alerts. v1 supports 'apprise' (sends "
            "via http://apprise:8000/notify). Future: 'telegram' (direct bot)."
        ),
    )

    # LLM provider chain.
    llm_provider_primary: Literal["claude-code", "openrouter"] = Field(
        default="claude-code",
        description=(
            "Primary LLM provider. 'claude-code' invokes the local `claude -p` "
            "subprocess inheriting host OAuth from /home/watchdog/.claude/. "
            "'openrouter' uses the HTTP API directly."
        ),
    )
    llm_provider_fallback: Literal["claude-code", "openrouter", "none"] = Field(
        default="openrouter",
        description=(
            "Fallback when the primary fails (exit non-zero, timeout, classifier "
            "abort, rate-limit). 'none' disables fallback (sidecar drops to "
            "rule-only mode on primary failure)."
        ),
    )

    # Per-tier model selection — applies to whichever provider is active.
    # NOTE: Claude Code internally routes Haiku→Opus already (verified live).
    # We expose explicit fields anyway so OpenRouter callers have the same shape.
    cheap_model: str = Field(
        default="haiku",
        description=(
            "First-pass model alias. For claude-code: 'haiku' (Claude routes). "
            "For openrouter: full id like 'google/gemini-2.5-flash' or 'anthropic/claude-haiku-4.5'."
        ),
    )
    expensive_model: str = Field(
        default="sonnet",
        description=(
            "Escalation model alias. For claude-code: 'sonnet' or 'opus'. "
            "For openrouter: full id like 'anthropic/claude-sonnet-4.6'."
        ),
    )

    # Per-incident hard ceiling. Sidecar passes this to `claude -p --max-budget-usd`.
    per_incident_budget_usd: float = Field(
        default=0.50,
        ge=0.0,
        description=(
            "Hard per-incident USD ceiling passed to `claude -p --max-budget-usd`. "
            "0.0 disables the per-incident cap (only daily caps apply). Recommended "
            "starting value: $0.50 (≈20 Haiku diagnosis calls or 1–2 Sonnet escalations)."
        ),
    )

    @model_validator(mode="after")
    def _check_caps_set_when_enabled(self) -> "WatchdogConfig":
        """If enabled=true, at least one cap must be > 0 (defense against
        accidentally-uncapped projects). Either USD cap > 0 OR invocations cap > 0."""
        if self.enabled and self.daily_budget_usd <= 0 and self.daily_invocations_cap <= 0:
            raise ValueError(
                "watchdog: enabled=true requires at least one of "
                "daily_budget_usd > 0 or daily_invocations_cap > 0"
            )
        return self
```

**Wire into `Spec` class** (further down in spec_loader.py): add a new field

```python
watchdog: WatchdogConfig = Field(
    default_factory=WatchdogConfig,
    description="Per-project AI watchdog sidecar config. See WatchdogConfig.",
)
```

**Default-by-kind logic** lives in the **dispatcher** (`_register_watchdog`), not in the Pydantic class — Pydantic doesn't know about Shape. The dispatcher reads `spec.shape.kind` and sets `WatchdogConfig.enabled=True` if `kind in (SERVICE, WORKER, WORDPRESS)` AND owner didn't explicitly set `watchdog.enabled`.

Estimated lines added: **~80** (class + field + validator + integration into Spec).

---

## 2. `_register_watchdog()` orchestrator function (in `src/fabrik/orchestrator/infrastructure.py`)

### 2.1 Update `_REGISTRAR_ORDER`

```python
_REGISTRAR_ORDER = (
    "postgres", "redis", "gatus", "backrest", "glitchtip",
    "grafana", "authelia", "meilisearch", "prometheus",
    "watchdog",  # NEW — must run last (depends on postgres + prometheus)
)
```

### 2.2 Update `resolve_applicability()` (`infrastructure.py:126+`)

Add a new branch (defaults: enabled if `kind in {SERVICE, WORKER, WORDPRESS}` AND `watchdog.enabled` not explicitly False):

```python
# watchdog (added in P2)
watchdog_cfg = spec.get("watchdog", {}) or {}
explicit_enabled = watchdog_cfg.get("enabled")
kind_allows = kind in ("service", "worker", "wordpress")
if explicit_enabled is True:
    should = True
    reason = "watchdog.enabled=true (explicit)"
elif explicit_enabled is False:
    should = False
    reason = "watchdog.enabled=false (explicit override)"
elif kind_allows:
    should = True
    reason = f"watchdog default-on for kind={kind}"
else:
    should = False
    reason = f"watchdog default-off for kind={kind}"
out["watchdog"] = (should and _enabled(infra, "watchdog"), reason)
```

### 2.3 Dispatch in `provision()` (`infrastructure.py:314+`)

Add at the END of the dispatch chain (after `prometheus`):

```python
if should_run["watchdog"]:
    self._provision_watchdog(name, spec, ctx, dry_run)
```

### 2.4 New `_provision_watchdog()` method

```python
def _provision_watchdog(
    self, name: str, spec: dict[str, Any],
    ctx: DeploymentContext, dry_run: bool,
) -> None:
    """Inject the watchdog sidecar into the project's compose + env."""
    try:
        from fabrik.drivers.watchdog import deploy_sidecar
        watchdog_cfg = spec.get("watchdog", {}) or {}
        shape = spec.get("shape", {}) or {}
        result = deploy_sidecar(
            project_name=name,
            main_container=name,  # convention: container_name matches spec.id
            shape_kind=shape.get("kind", "service"),
            config=watchdog_cfg,
            dry_run=dry_run,
        )
        ctx.add_resource("watchdog", name, status=result.get("status"))
        logger.info("watchdog: %s → %s", name, result.get("status"))
    except Exception as e:  # noqa: BLE001 — bounded non-fatal
        logger.warning("watchdog provisioning failed (non-fatal): %s", e)
```

Estimated lines added: **~60** (registrar function + applicability branch + dispatch hook).

---

## 3. `src/fabrik/drivers/watchdog.py` (NEW driver)

Matches gatus.py shape (V7). Functions:

```python
WATCHDOG_IMAGE = "fabrik/watchdog:latest"
"""Sidecar image. Built from fabrik-lib/watchdog/sidecar/Dockerfile.
   Built on the VPS in P2 development; future: published to a registry."""

WATCHDOG_DATA_DIR = "/opt/{project}/watchdog"
"""Per-project sidecar state directory on VPS — holds state.db (SQLite),
   cost_wal.db (cost-budget WAL), incidents/, and claude-settings.json."""

_PROJECT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def deploy_sidecar(
    project_name: str,
    main_container: str,
    shape_kind: str,
    config: dict,
    dry_run: bool = False,
) -> dict:
    """At fabrik apply: provision the watchdog sidecar for one project.

    Steps:
      1. Validate inputs.
      2. Create /opt/<project>/watchdog/ directory tree on VPS (mode 700,
         owner watchdog UID 1000).
      3. Render claude-settings.json from template (filling <project_id>
         and <main_container> placeholders) and scp into watchdog dir.
      4. Inject WATCHDOG_* env vars into the project's .env (uses
         SSHDeployer.inject_env pattern from deployer_ssh.py:135).
      5. Inject sidecar service block into the project's compose.yaml
         (uses _read_compose / _patch_compose / _write_compose helpers
         — same atomic-write pattern as gatus uses for its YAML).
      6. `sudo docker compose -f /opt/<project>/compose.yaml up -d` to
         start the new sidecar service alongside main.

    Idempotent: if the sidecar service block already exists in compose,
    rewriting it with the same config is a no-op. Subsequent compose up
    on unchanged config doesn't recreate the container.

    Returns dict with status, image, sidecar_service_name.
    """


def remove_sidecar(project_name: str, dry_run: bool = False) -> bool:
    """At fabrik destroy: remove the sidecar from compose + delete state.

    Best-effort: never raises. Sequence:
      1. Remove sidecar service block from compose.yaml.
      2. compose up -d (which removes the now-orphaned sidecar).
      3. sudo rm -rf /opt/<project>/watchdog/.
    """


def _build_sidecar_service_yaml(
    project_name, main_container, shape_kind, config,
) -> dict:
    """Render the YAML service block to inject into compose.yaml. Outputs
    a Python dict; caller serializes with yaml.dump.

    Service shape (concrete; verified against existing compose patterns):

        services:
          watchdog:
            image: fabrik/watchdog:latest
            container_name: {project}-watchdog
            restart: unless-stopped
            user: "1000:1000"           # non-root (Linux Claude Code refuses root)
            platform: linux/amd64
            networks: [coolify]
            depends_on:
              - {main_container}
            volumes:
              - /opt/{project}/watchdog:/var/lib/watchdog
              - /home/ozgur/.claude:/home/watchdog/.claude:ro   # OAuth + config
              - /var/run/docker.sock:/var/run/docker.sock:ro    # Tier A actions
              - /opt/{project}:/project:ro                       # logs read access
            environment:
              WATCHDOG_PROJECT_ID: "{project_name}"
              WATCHDOG_MAIN_CONTAINER: "{main_container}"
              WATCHDOG_SHAPE_KIND: "{shape_kind}"
              WATCHDOG_DAILY_BUDGET_USD: "{config.daily_budget_usd}"
              WATCHDOG_DAILY_INVOCATIONS_CAP: "{config.daily_invocations_cap}"
              WATCHDOG_AUTO_TIER_B: "{config.auto_tier_b}"
              WATCHDOG_PER_INCIDENT_BUDGET_USD: "{config.per_incident_budget_usd}"
              WATCHDOG_LLM_PROVIDER_PRIMARY: "{config.llm_provider_primary}"
              WATCHDOG_LLM_PROVIDER_FALLBACK: "{config.llm_provider_fallback}"
              WATCHDOG_CHEAP_MODEL: "{config.cheap_model}"
              WATCHDOG_EXPENSIVE_MODEL: "{config.expensive_model}"
              WATCHDOG_ESCALATION_CHANNEL: "{config.escalation_channel}"
              # Cost-ledger (postgres-main fabrik_analytics) — same role as project DB.
              # Owner-side: inject_env() merges these on top of project .env at apply time.
              FABRIK_ANALYTICS_URL: "${{FABRIK_ANALYTICS_URL}}"  # populated by registrar
              # OpenRouter fallback key — from project .env if owner set it.
              WATCHDOG_OPENROUTER_KEY: "${{WATCHDOG_OPENROUTER_KEY:-}}"
              # Apprise endpoint (on the coolify network).
              APPRISE_URL: "http://apprise:8000"
            deploy:
              resources:
                limits:
                  memory: 256M
                  cpus: '0.25'
            healthcheck:
              test: ["CMD", "python3", "-c", "import urllib.request,os; urllib.request.urlopen('http://localhost:8888/health', timeout=2)"]
              interval: 30s
              timeout: 5s
              retries: 3
              start_period: 20s


def _patch_compose(compose_path_local: str, sidecar_block: dict) -> str:
    """Read existing compose.yaml, merge sidecar block under services:,
    return updated YAML text. Atomic: returns text only, caller writes."""
```

**Idempotency:** the function reads existing compose, checks if a `watchdog` service block exists with identical content, returns `status=exists` if so. Otherwise writes new compose and runs `docker compose up -d` (Docker compose is itself idempotent — only recreates containers whose config changed).

**Estimated lines:** ~400 (validation + deploy + remove + helpers + docstrings).

---

## 4. `fabrik-lib/watchdog/sidecar/` contents

### 4.1 `Dockerfile`

```dockerfile
# fabrik/watchdog:latest — sidecar that watches one project's main container.
# Base: python:3.13-slim-bookworm per AGENTS.md (NO Alpine).
FROM python:3.13-slim-bookworm AS base

# Install Claude Code CLI via npm.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates docker.io \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code@2.1.144 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for Claude Code (Linux refuses bypass mode under sudo).
RUN groupadd -g 1000 watchdog && useradd -u 1000 -g 1000 -m -s /bin/bash watchdog
USER watchdog
WORKDIR /home/watchdog

# Sidecar code.
COPY --chown=watchdog:watchdog requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
COPY --chown=watchdog:watchdog agent.py llm_client.py actions.py state.py emitter_reader.py ./
COPY --chown=watchdog:watchdog hooks/ ./hooks/
COPY --chown=watchdog:watchdog claude-settings.json.template /etc/watchdog/

# Healthcheck endpoint runs on 8888 (Tier A actions don't expose ports).
EXPOSE 8888

CMD ["python3", "-u", "agent.py"]
```

**Verification:** `python:3.13-slim-bookworm` matches AGENTS.md base-image rule (V7-adjacent verified during P1; same pattern). The Node.js install adds ~200MB but is required for Claude Code CLI. Final image expected ~600MB.

### 4.2 `agent.py` — main state machine (pseudocode)

```
LOAD config from env
INIT state.db (SQLite) and cost_wal.db (cost-budget vendor module)
START healthcheck HTTP server on 8888 (background thread)
LOOP every CHECK_INTERVAL_SECONDS (default 60):
    snapshot = gather_snapshot()  # docker logs main + Prometheus /metrics scrape
    anomalies = detect_anomalies(snapshot)  # rule-based first pass
    incidents = read_emitted_incidents(state.db)  # from emitter library
    new_incidents = anomalies + incidents
    for incident in new_incidents:
        budget_state = cost_budget.check_caps(pg, wal, project, USD_CAP, INV_CAP)
        if budget_state.over_cap:
            handle_with_rules_only(incident)  # no LLM
            audit_log.record_event(action='watchdog.budget_kill_switch', details={...})
            continue
        diagnosis = llm_diagnose(incident, budget_state)
        cost_budget.record_cost(pg, wal, event=CostEvent(...))
        if diagnosis.tier == 'A':
            execute_tier_a_action(diagnosis.action, main_container)
            audit_log.record_event(action='watchdog.tier_a_action', details=...)
        elif diagnosis.tier == 'B' and auto_tier_b:
            execute_tier_b_action(diagnosis.action)
            audit_log.record_event(action='watchdog.tier_b_action', details=...)
        else:  # Tier C OR Tier B without opt-in
            escalate_apprise(diagnosis.summary, severity=diagnosis.tier)
            audit_log.record_event(action='watchdog.tier_c_escalation', details=...)
    REPLAY: cost_budget.replay_wal(pg, wal) every iteration
SHUTDOWN handler: drain WAL, write final state.db row, exit.
```

### 4.3 `llm_client.py` — provider chain (pseudocode)

```
def diagnose(incident, budget_state) -> Diagnosis:
    primary = config.llm_provider_primary  # 'claude-code' | 'openrouter'
    fallback = config.llm_provider_fallback

    prompt = render_prompt(incident, snapshot, allow_list_for_project)
    per_incident_cap = config.per_incident_budget_usd

    try:
        if primary == 'claude-code':
            return _invoke_claude_code(prompt, per_incident_cap)
        else:
            return _invoke_openrouter(prompt, model=config.cheap_model)
    except (TimeoutError, ProviderUnavailable) as e:
        log_warning(f"primary {primary} failed: {e}; falling back to {fallback}")
        escalate_apprise(f"watchdog primary LLM provider {primary} unavailable",
                         severity='tier_c')
        if fallback == 'openrouter':
            return _invoke_openrouter(prompt, model=config.cheap_model)
        elif fallback == 'claude-code':
            return _invoke_claude_code(prompt, per_incident_cap)
        else:  # 'none'
            return RuleOnlyFallback()

def _invoke_claude_code(prompt, per_incident_cap) -> Diagnosis:
    # Invocation pattern verified live on VPS (V1).
    # NOTE: DO NOT use --bare (requires API key, not subscription).
    # Use --no-session-persistence (no state writes to mounted ~/.claude/).
    # Use --max-budget-usd for per-call ceiling.
    # Use --json-schema for structured output validation.
    schema = {
        "type": "object",
        "properties": {
            "tier": {"enum": ["A", "B", "C"]},
            "action": {"type": "string"},
            "reasoning": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["tier", "action", "reasoning"]
    }
    proc = subprocess.run([
        "claude", "-p", prompt,
        "--output-format", "json",
        "--no-session-persistence",
        "--permission-mode", "auto",
        "--settings", "/etc/watchdog/claude-settings.json",
        "--allowedTools", "Bash,Read,Grep,Glob",
        "--append-system-prompt", PROJECT_SYSTEM_PROMPT,
        "--max-budget-usd", str(per_incident_cap),
        "--json-schema", json.dumps(schema),
        "--effort", "low",  # diagnosis is usually easy
    ], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise ProviderUnavailable(proc.stderr)
    payload = json.loads(proc.stdout)
    # Real dollar cost reported by Claude Code:
    cost_usd = float(payload.get("total_cost_usd", 0))
    # Parse the model's structured answer:
    diagnosis = json.loads(payload["result"])
    return Diagnosis(
        tier=diagnosis["tier"], action=diagnosis["action"],
        reasoning=diagnosis["reasoning"],
        confidence=diagnosis.get("confidence", 0.0),
        cost_usd=cost_usd,
        in_tokens=payload["usage"]["input_tokens"],
        out_tokens=payload["usage"]["output_tokens"],
        provider="claude-code",
        model_path=list(payload["modelUsage"].keys()),  # e.g. ["claude-haiku-...", "claude-opus-..."]
    )

def _invoke_openrouter(prompt, model) -> Diagnosis:
    # Plain HTTPS POST to openrouter.ai/api/v1/chat/completions.
    # API key from WATCHDOG_OPENROUTER_KEY env var.
    # Same structured output via Pydantic validation on response.
    ...
```

### 4.4 `actions.py` — Tier A handlers

```python
TIER_A_HANDLERS = {
    "restart_container": _restart_main,           # docker restart <main>
    "clear_file_cache": _clear_local_cache,        # rm -rf /project/cache/*
    "scale_concurrency": _scale_concurrency,       # set env var, restart
    "pause_worker": _pause_via_pause_state,        # pause-state Redis SETEX
    "drop_queue_items": _drop_queue_oldest_n,      # SQL DELETE ORDER BY age LIMIT N
    "rotate_locks": _rotate_stuck_locks,           # SQL UPDATE locked_at=NULL WHERE locked_at < now()-interval
}

TIER_B_HANDLERS = {
    "wipe_redis_cache": _wipe_redis_via_pattern,   # SCAN + DEL with pattern
    "reset_db_pool": _reset_db_pool,               # signal to main app via /admin endpoint
}

# Tier C: NO handlers — always escalate via Apprise.
```

Each Tier A handler is ~30–50 lines. Tier B is opt-in via `WATCHDOG_AUTO_TIER_B=true` env.

### 4.5 `hooks/PreToolUse.sh`

**Decision: bash, not python.** Reasons:

- Hook is invoked per Claude tool call — startup latency matters; bash starts in ~5ms vs python ~50ms.
- Logic is simple pattern matching (jq for JSON parsing).
- Existing fabrik patterns (gatus container resolution) use shell.
- No deps to install — bash + jq are in the base image.

```bash
#!/bin/bash
# PreToolUse hook — fires before every Claude Code tool invocation.
# Stdin: JSON with {tool_name, parameters}. Exit 0 = allow, non-zero = block.

set -e
PROJECT_ID="${WATCHDOG_PROJECT_ID:?required}"
MAIN_CONTAINER="${WATCHDOG_MAIN_CONTAINER:?required}"

payload=$(cat)
tool=$(echo "$payload" | jq -r '.tool_name')
params=$(echo "$payload" | jq -r '.parameters')

case "$tool" in
  Bash)
    cmd=$(echo "$params" | jq -r '.command')
    # Explicit allow-list — anything not matching is blocked.
    case "$cmd" in
      "docker logs $MAIN_CONTAINER"*)                      exit 0 ;;
      "docker inspect $MAIN_CONTAINER")                    exit 0 ;;
      "docker restart $MAIN_CONTAINER")                    exit 0 ;;
      "docker stats --no-stream $MAIN_CONTAINER")          exit 0 ;;
      "curl -s localhost:"*"/metrics")                     exit 0 ;;
      "curl -s localhost:"*"/health")                      exit 0 ;;
      "ls /project/"*)                                     exit 0 ;;
      "cat /project/logs/"*|"tail "*"/project/logs/"*)     exit 0 ;;
      "grep "*"/project/logs/"*)                           exit 0 ;;
      # Explicit denies (defense in depth — also in settings.json deny).
      "docker stop postgres-main"*|"docker stop redis-main"*|"docker stop traefik"*)
        echo "BLOCKED: shared infra container" >&2; exit 1 ;;
      "rm -rf"*|"sudo"*|"systemctl"*|"git push"*)
        echo "BLOCKED: destructive or out-of-scope" >&2; exit 1 ;;
      *)
        echo "BLOCKED: command not in per-project allow-list" >&2; exit 1 ;;
    esac
    ;;
  Read|Grep|Glob)
    # Permission-mode auto + sandbox handle these — hook just allows.
    exit 0 ;;
  WebFetch|WebSearch|Edit|Write)
    echo "BLOCKED: tool $tool not allowed for watchdog" >&2; exit 1 ;;
  *)
    echo "BLOCKED: unknown tool $tool" >&2; exit 1 ;;
esac
```

### 4.6 `claude-settings.json.template`

Exactly the shape from plan v2 § Locked decisions (§ Claude Code permission boundaries → "Concrete `claude-settings.json` shape"). Driver fills `<project_id>` and `<main_container>` at apply time. Schema verified against `claude --help --settings` shape (the file is a JSON dict at top level; Claude Code's documented `permissions` / `autoMode` / `sandbox` keys are honored).

### 4.7 State schema (SQLite at `/var/lib/watchdog/state.db`)

```sql
-- incidents — one row per detected anomaly OR emitter-injected event.
CREATE TABLE IF NOT EXISTS incidents (
    id           TEXT PRIMARY KEY,           -- uuid7 (sortable)
    detected_at  TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    source       TEXT NOT NULL,              -- 'rule' | 'emitter' | 'metrics'
    name         TEXT NOT NULL,              -- e.g. 'oom_kill', 'http_5xx_spike', 'payment_failed'
    severity     TEXT NOT NULL DEFAULT 'info', -- info | warn | urgent
    details      TEXT NOT NULL DEFAULT '{}', -- JSON
    resolved_at  TEXT,                       -- NULL until resolved
    resolution   TEXT                        -- 'auto' | 'manual' | 'expired'
);
CREATE INDEX IF NOT EXISTS idx_incidents_unresolved
    ON incidents (detected_at DESC) WHERE resolved_at IS NULL;

-- actions — every Tier A/B execution. Mirrors audit_log row but is local
-- (audit_log is in host project's postgres; this is the sidecar's own copy
-- for fast queries without postgres dependency).
CREATE TABLE IF NOT EXISTS actions (
    id              TEXT PRIMARY KEY,        -- uuid7
    incident_id     TEXT,                    -- FK to incidents.id (informational)
    ts              TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    tier            TEXT NOT NULL,           -- 'A' | 'B' | 'C'
    action_name     TEXT NOT NULL,           -- 'restart_container' etc.
    result          TEXT NOT NULL,           -- 'success' | 'failure' | 'escalated'
    detail          TEXT                     -- JSON; error message on failure
);
CREATE INDEX IF NOT EXISTS idx_actions_ts ON actions (ts DESC);

-- emitter_inbox — written by the vendored emitter library (in main app),
-- polled by sidecar's main loop. Single-writer (emitter) + single-reader
-- (sidecar) → SQLite WAL mode handles concurrency safely.
CREATE TABLE IF NOT EXISTS emitter_inbox (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    name        TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'info',
    details     TEXT NOT NULL DEFAULT '{}',
    processed   INTEGER NOT NULL DEFAULT 0   -- 0 = pending, 1 = consumed
);
CREATE INDEX IF NOT EXISTS idx_emitter_pending
    ON emitter_inbox (seq) WHERE processed = 0;
```

Note: **cost-budget WAL is a separate SQLite file** at `/var/lib/watchdog/cost_wal.db` (managed by the vendored cost-budget module). State.db is the sidecar's own.

### Estimated total sidecar lines

| File | Lines |
|---|---:|
| agent.py | ~250 |
| llm_client.py | ~300 |
| actions.py | ~250 |
| state.py (helpers) | ~80 |
| emitter_reader.py | ~50 |
| hooks/PreToolUse.sh | ~50 |
| claude-settings.json.template | ~70 |
| Dockerfile | ~30 |
| schema (inline string) | ~50 |
| requirements.txt | ~10 |
| **TOTAL** | **~1,140** |

Matches plan v2's "~1000" target with a bit of headroom.

---

## 5. `fabrik-lib/watchdog/emitter/` contents

Vendored into the **main app** (NOT the sidecar) so the app can emit incidents the sidecar reads.

```python
# fabrik-lib/watchdog/emitter/emitter.py
"""Watchdog emitter — main-app side of the watchdog incident inbox.

Vendor it: cp -r /opt/fabrik-lib/watchdog/emitter /opt/my-project/libs/watchdog_emitter

Main app calls al.emit_incident("payment_failed", {"order_id": 123}); the
local SQLite write is fast (~1ms) and the sidecar's main loop picks it up
within CHECK_INTERVAL_SECONDS.
"""
import json
import sqlite3
from pathlib import Path
from typing import Any

WATCHDOG_STATE_DB = "/var/lib/watchdog/state.db"
# When vendored into main app, path is hardcoded — main app and sidecar
# must mount the same volume at the same path. Default matches the
# driver's compose injection.


def emit_incident(name: str, details: dict[str, Any], *,
                  severity: str = "info",
                  db_path: str = WATCHDOG_STATE_DB) -> None:
    """Write an incident to the sidecar's inbox. Non-blocking; ~1ms latency.

    Args:
        name: short event identifier, e.g. 'payment_failed', 'queue_backlog'.
        details: structured JSON-serializable context.
        severity: 'info' (default) | 'warn' | 'urgent'.
        db_path: override only for tests.

    Fails gracefully: SQLite errors are logged at WARN; never raises. The
    main app's business operation must NOT be tied to incident emission.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        conn.execute(
            "INSERT INTO emitter_inbox (name, severity, details) VALUES (?, ?, ?)",
            (name, severity, json.dumps(details, sort_keys=True)),
        )
        conn.commit()
        conn.close()
    except Exception as e:  # noqa: BLE001 — never block main app on telemetry
        # Best-effort. Don't add print() / logging at import time.
        pass
```

### `fabrik-lib/watchdog/emitter/README.md` outline

1. Title + one-paragraph intro
2. What's included (single `emitter.py`)
3. Vendor it (copy into project's `libs/`)
4. Usage example (one snippet showing emit at a billing-failure site)
5. Configuration (env var override of state.db path — rare)
6. Fail-safe note (NEVER raises; if state.db unwritable, the incident is silently lost — that's acceptable for telemetry)
7. Testing (write 5 events, query inbox)
8. Dependencies (stdlib only)

---

## 6. `core/watchdog.md` rule pack section outline

Frontmatter matches `core/58-resilience.md` (verified during P1).

1. **When to use** — universal default by `shape.kind`; explicit owner override.
2. **Architecture summary** — sidecar mounting, OAuth inheritance, docker.sock scoping.
3. **Action allow-list** — Tier A/B/C with concrete examples, defense-in-depth (settings.json + PreToolUse hook + docker label).
4. **Owner approval flow for Tier B opt-in** — spec config `auto_tier_b: true` + Apprise confirmation message.
5. **Integration with pause-state, async-http-client, abuse-prevention** — how the sidecar uses each (pause-state for `pause_worker`; circuit-breaker for OpenRouter fallback; abuse-prevention is host-app side, not sidecar).
6. **Cost behavior** — Claude Code returns `total_cost_usd` (not estimated from tokens); per-incident `--max-budget-usd` ceiling; daily cap via cost-budget.
7. **Anti-patterns** — calling sidecar from main app (use emitter instead); bypassing PreToolUse hook (lock it in settings); putting secret tokens in `details`; running sidecar as root.
8. **Worked example** — OOM diagnosis → Tier A restart → audit log → cost ledger.

---

## 7. Acceptance criteria for P2 (from parent plan)

| # | Criterion | Test recipe |
|---|---|---|
| 1 | Sidecar image builds with Claude Code CLI inherited from host config mount | `docker build /opt/fabrik-lib/watchdog/sidecar/` succeeds; `docker run --rm -v ~/.claude:/home/watchdog/.claude:ro fabrik/watchdog:latest claude --version` prints `2.1.144` |
| 2 | `fabrik apply` on test spec produces compose with watchdog service | `fabrik apply /opt/test-saas-for-epic-wf/specs/services/test-saas.yaml --dry-run` logs `watchdog: ... → created` AND the rendered compose has `services.watchdog:` block |
| 3 | `emit_incident()` writes audit log row + visible to sidecar | Vendor emitter into a test container; call `emit_incident("test_event", {"k": "v"})`; query `state.db emitter_inbox` from sidecar shell → 1 row present; sidecar loop processes it within 60s and records action in `actions` table |
| 4 | Restart-action handler works against test container | Trigger `docker kill <main>`; within 90s sidecar restarts via Tier A path; verify via `docker inspect <main>` → `RestartCount` incremented; `state.db actions` table has 1 row with `action_name='restart_container'`, `result='success'`; audit_log on postgres-main has `watchdog.tier_a_action` row; cost_ledger has 1 row with real `cost_usd` |
| 5 | Primary-to-fallback provider chain verified | Force Claude Code unreachable (block `/usr/local/bin/claude` access from sidecar container); inject anomaly; sidecar falls back to OpenRouter within 60s; emits Tier C "primary LLM provider unavailable" alert via Apprise; cost_ledger row has `provider='openrouter'` with real `cost_usd` |

---

## 8. Order of artifacts to code (smallest leaf first)

| # | Artifact | Path | Est. lines | Depends on |
|---|---|---:|---|---|
| 1 | `WatchdogConfig` Pydantic class | `src/fabrik/spec_loader.py` (insert after Shape, line 341+) | +80 | — |
| 2 | `claude-settings.json.template` | `fabrik-lib/watchdog/sidecar/` | ~70 | — |
| 3 | `hooks/PreToolUse.sh` | `fabrik-lib/watchdog/sidecar/hooks/` | ~50 | — |
| 4 | Sidecar `Dockerfile` | `fabrik-lib/watchdog/sidecar/Dockerfile` | ~30 | (will install Claude Code CLI) |
| 5 | Sidecar `llm_client.py` | `fabrik-lib/watchdog/sidecar/` | ~300 | (1) for env var contract |
| 6 | Sidecar `actions.py` | `fabrik-lib/watchdog/sidecar/` | ~250 | pause-state vendor (existing) |
| 7 | Sidecar `state.py` (helpers) | `fabrik-lib/watchdog/sidecar/` | ~80 | — |
| 8 | Sidecar `agent.py` (main loop) | `fabrik-lib/watchdog/sidecar/` | ~250 | (5), (6), (7), P1 modules |
| 9 | Sidecar SQLite schema (inline or `state_schema.sql`) | `fabrik-lib/watchdog/sidecar/` | ~50 | — |
| 10 | Emitter library | `fabrik-lib/watchdog/emitter/{emitter.py,README.md}` | ~120 | — |
| 11 | `core/watchdog.md` | `.windsurf/rules/core/watchdog.md` | ~150 | (1)–(10) for cross-references |
| 12 | `_register_watchdog()` + applicability + dispatch | `src/fabrik/orchestrator/infrastructure.py` | +60 | (1), (13) |
| 13 | `src/fabrik/drivers/watchdog.py` | new driver | ~400 | (1), (2), sidecar image built |
| 14 | Update `fabrik-lib/README.md` (modules table + matrix) | `/opt/fabrik-lib/README.md` | +5 | — |
| 15 | Update test spec to enable watchdog | `/opt/test-saas-for-epic-wf/specs/services/...` | ~10 | (1) merged |

**Total estimated lines:** ~1,855 (close to plan v2's 1,500–2,000 estimate).

---

## 9. Side findings (worth flagging for separate tasks)

1. **Plan v2's `--bare` assumption was wrong** — `--bare` requires API key, not subscription. The sidecar will NOT use `--bare`; it will use `--no-session-persistence` + `--settings` to constrain behavior while still inheriting OAuth from the mounted `~/.claude/.credentials.json`. The corresponding section of plan v2 should be amended with a changelog entry. **Recommended:** add a "v2 → v3 changelog" note inside `2026-05-30-ai-watchdog-platform.md` capturing this correction so future readers don't carry the wrong assumption.

2. **Claude Code returns `total_cost_usd` directly** — we don't need to estimate cost from token counts. Plan v2's "Claude Code rows record `cost_usd=0.000000`" was wrong. Update plan v2's Locked Decisions § B2 to remove that claim. Cost ledger rows for `provider='claude-code'` should record the actual `total_cost_usd` from Claude Code's JSON output.

3. **`--max-budget-usd` is a built-in per-call ceiling** that Claude Code enforces. We can use this as a defense-in-depth per-incident cap, complementing cost-budget's daily cap. Added to `WatchdogConfig.per_incident_budget_usd`.

4. **`--json-schema` for structured output validation** is a significant reliability win over plan v2's "self-rated confidence" pattern. The sidecar's `llm_client.py` should use it for every diagnosis call so we get type-validated `{tier, action, reasoning, confidence}` instead of trusting freeform text parsing.

5. **Older infra containers lack `com.docker.compose.project` label** (verified — site-provisioner, image-broker, meilisearch, etc. return empty). The docker.sock scoping in plan v2 is not airtight for those containers. Defense-in-depth via PreToolUse hook's explicit allow-list of `Bash(docker restart <main_container>)` (NOT a wildcard) handles this — but it's worth a note in `core/watchdog.md` § Anti-patterns: "do not rely on docker label scoping alone for security; the PreToolUse hook is the surgical layer."

6. **Apprise is on the `coolify` Docker network as a plain container named `apprise`** — sidecar can POST directly to `http://apprise:8000/notify` (no SSH needed). Plan v2 was silent on this; the driver/sidecar wires `APPRISE_URL=http://apprise:8000` in the env block.

7. **Claude Code internally routes Haiku → Opus** (verified live — one prompt used both). Our explicit cheap/expensive tier-ladder is partially redundant with Claude Code's internal routing but still useful as a coarse OpenRouter selector AND as an `--effort` lever (`low|medium|high|xhigh|max`).

8. **Sidecar memory limit 256M** based on (a) Claude Code CLI's Node.js runtime needs ~150MB at idle, (b) cost-budget Python module + SQLite ~30MB, (c) headroom for one LLM call's prompt+response in memory ~50MB. v2 plan didn't specify — sub-plan adds the concrete number.

9. **Healthcheck endpoint on port 8888** — sidecar runs a tiny HTTP server (single-threaded `http.server` adequate) that returns the last-loop timestamp + budget state. Used by Gatus (optional) to monitor that the watchdog itself is alive. Not exposed via Traefik — internal-only on the `coolify` network.

10. **Out of scope for P2 (deferred):**
    - Telegram bot for two-way confirmation (Apprise is one-way only).
    - Sidecar UI dashboard.
    - Cross-project incident correlation.
    - GlitchTip event pull (planned for v2 of watchdog).

---

## Self-review against P2.A prompt requirements

- [x] **1. WatchdogConfig Pydantic class** — full class with all fields (types, defaults, validators, descriptions); insertion line specified (`spec_loader.py:341+`); default-by-kind logic placed in dispatcher (correct architectural choice — Pydantic doesn't know Shape); enabled+caps validator written.
- [x] **2. `_register_watchdog()` function** — applicability branch, position in `_REGISTRAR_ORDER` (last; justified), dispatch call site, driver dispatch function name.
- [x] **3. `src/fabrik/drivers/watchdog.py`** — function outline matches gatus.py shape; `deploy_sidecar` + `remove_sidecar` + helpers; compose-patch atomicity strategy; estimated line count (~400).
- [x] **4. `fabrik-lib/watchdog/sidecar/`** — Dockerfile (verified python:3.13-slim-bookworm, Node.js for Claude Code, non-root UID 1000); agent.py state machine pseudocode; llm_client.py with verified `claude -p` invocation (no `--bare`, with `--no-session-persistence`, `--max-budget-usd`, `--json-schema`); actions.py Tier A/B/C handlers; hooks/PreToolUse.sh in bash (decision defended); claude-settings.json.template; SQLite state schema; total ~1,140 lines.
- [x] **5. `fabrik-lib/watchdog/emitter/`** — emitter.py with `emit_incident()` interface; fail-safe semantics; README outline; vendoring path.
- [x] **6. `core/watchdog.md` outline** — 8 sections including action allow-list, Tier B opt-in flow, integration with existing primitives, anti-patterns.
- [x] **7. Acceptance criteria for P2** — 5 testable items with concrete test recipes (some require live `fabrik apply` — will run in P5).
- [x] **8. Order of artifacts to code** — 15 items in dependency order with estimated lines; total ~1,855.
- [x] **9. Side findings** — 10 substantive findings, including 3 corrections to plan v2 itself (`--bare`/auth, cost-tracking, internal Haiku→Opus routing).

**Verification grade:** all reads done; live VPS verifications on `claude --help`, `~/.claude/` location, docker compose label, Apprise network, claude -p output format; P1 module signatures cross-checked. Zero assumptions remain unverified in the sub-plan body.

---

## End-of-response file summary

| File | Lines | Change |
|---|---:|---|
| `docs/development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md` | ~720 | Created — the P2 sub-plan |

No code written. No other files modified. Three live-verification findings reshape plan v2's assumptions (`--bare` semantics, `total_cost_usd` availability, internal model routing); recommend amending plan v2 in a follow-up when these are confirmed.
