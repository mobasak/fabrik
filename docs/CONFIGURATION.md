# Configuration

**Last Updated:** 2026-01-07

All Fabrik configuration options.

## Environment Variables

### VPS Connection

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VPS_HOST` | Yes | VPS IP or hostname | `172.93.160.197` |
| `VPS_USER` | Yes | SSH user | `deploy` |
| `VPS_SSH_KEY` | No | Path to SSH key | `~/.ssh/id_rsa` |

### Coolify API

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `COOLIFY_API_URL` | Yes | Coolify dashboard URL | `https://coolify.example.com` |
| `COOLIFY_API_TOKEN` | Yes | API token from Coolify | `token_xxx` |

### Namecheap DNS

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NAMECHEAP_API_USER` | Yes | API username | `youruser` |
| `NAMECHEAP_API_KEY` | Yes | API key | `xxx` |
| `NAMECHEAP_CLIENT_IP` | Yes | Your whitelisted IP | `1.2.3.4` |

### Cloudflare DNS (Phase 4+)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `CLOUDFLARE_API_TOKEN` | No | API token | `xxx` |
| `CLOUDFLARE_ZONE_ID` | No | Zone ID | `xxx` |

### Backblaze B2 (Backups)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `B2_KEY_ID` | Yes | Application key ID | `xxx` |
| `B2_APPLICATION_KEY` | Yes | Application key | `xxx` |
| `B2_BUCKET_NAME` | Yes | Bucket for backups | `fabrik-backups` |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | No | `json` | `json` or `text` |

### Automation & Notifications

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FABRIK_NOTIFY_SCRIPT` | No | `~/.factory/hooks/notify.sh` | Path to notification script used by the review processor and docs updater; receives `{"message": "<text>"}` on stdin |
| `FABRIK_ROOT` | No | `/opt/fabrik` | Base path used when resolving review/docs queue, results, and config paths |
| `FABRIK_REVIEW_QUEUE` | No | `${FABRIK_ROOT}/.droid/review_queue` | Directory where review tasks are queued |
| `FABRIK_REVIEW_RESULTS` | No | `${FABRIK_ROOT}/.droid/review_results` | Directory where completed reviews are stored |
| `FABRIK_DOCS_QUEUE` | No | `${FABRIK_ROOT}/.droid/docs_queue` | Directory where documentation update tasks are queued |
| `FABRIK_DOCS_LOG` | No | `${FABRIK_ROOT}/.droid/docs_log` | Directory where documentation update logs/results are stored |
| `FABRIK_MODELS_CONFIG` | No | `${FABRIK_ROOT}/config/models.yaml` | Override path for the models configuration used for model selection, rankings, and scenarios (used by `droid_models.py`, `review_processor.py`, etc.) |

### config/models.yaml

Model registry and stack rankings:

```yaml
version: "2026-01-06"
default_model: "claude-sonnet-4-5-20250929"

models:
  gpt-5.1-codex-max:
    provider: openai
    cost_tier: high
    cost_multiplier: 0.5
    reasoning_levels: ["low", "medium", "high", "extra_high"]
    default_reasoning: "medium"

stack_rank:
  1:
    model: gpt-5.1-codex-max
    why: Best for complex coding and refactoring
```

## Config Files

### config/platform.yaml

Main platform configuration:

```yaml
vps:
  host: ${VPS_HOST}
  user: ${VPS_USER}

coolify:
  url: ${COOLIFY_API_URL}

dns:
  provider: namecheap  # or cloudflare

backup:
  provider: b2
  schedule: "0 2 * * *"  # 2 AM daily
```

### specs/*.yaml

App specification files. See [Deployment](DEPLOYMENT.md) for spec format.

## File Locations

| Path | Purpose |
|------|---------|
| `.env` | Environment variables (gitignored) |
| `.env.example` | Template for .env |
| `config/` | YAML configuration files |
| `specs/` | App specification files |
| `templates/` | Compose templates |
