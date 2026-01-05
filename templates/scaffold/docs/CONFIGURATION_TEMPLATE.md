# Configuration

**Last Updated:** YYYY-MM-DD

---

## Quick Setup

```bash
cp .env.example .env
# Edit .env with your values
```

---

## Environment Variables

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `DATABASE_POOL_SIZE` | No | `5` | Connection pool size |
| `DATABASE_TIMEOUT` | No | `30` | Query timeout in seconds |

### API Keys

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | Yes | - | Main API authentication key |
| `SECRET_KEY` | Yes | - | JWT signing secret |
| `EXTERNAL_API_KEY` | No | - | Third-party service key |

### Feature Flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_FEATURE_X` | No | `false` | Enable experimental feature X |
| `DEBUG_MODE` | No | `false` | Enable debug logging |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | No | `json` | Log format (json, text) |
| `LOG_FILE` | No | `logs/app.log` | Log file path |

### External Services

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | - | Redis connection string |
| `SMTP_HOST` | No | - | Email server host |
| `SMTP_PORT` | No | `587` | Email server port |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Environment variables (not committed) |
| `.env.example` | Template for .env (committed) |
| `config/config.yaml` | Application settings |
| `config/logging.yaml` | Logging configuration |

---

## Environment-Specific Settings

### Development

```bash
DEBUG_MODE=true
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://localhost:5432/myapp_dev
```

### Production

```bash
DEBUG_MODE=false
LOG_LEVEL=INFO
DATABASE_URL=postgresql://prod-host:5432/myapp
```

---

## Configuration Checklist

Before running the application:

- [ ] `.env` file created from `.env.example`
- [ ] `DATABASE_URL` set and database accessible
- [ ] `SECRET_KEY` set (use `openssl rand -hex 32` to generate)
- [ ] `API_KEY` set if using external APIs
- [ ] Log directory exists and is writable
- [ ] All required environment variables set
