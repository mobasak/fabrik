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

### Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | No | `8000` | Server port |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Database (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | - | PostgreSQL connection string (enables DB features) |

### Feature Flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_FEATURE_X` | No | `false` | Enable experimental feature X |
| `DEBUG_MODE` | No | `false` | Enable debug logging |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
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
- [ ] `PORT` set (default: 8000)
- [ ] `DATABASE_URL` set if using database features
- [ ] Log directory exists and is writable (if using file logging)
