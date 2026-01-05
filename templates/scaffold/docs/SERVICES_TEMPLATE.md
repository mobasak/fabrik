# Required Services

> This document lists all services needed for this project to function.
> Update whenever you add, remove, or modify a service.

## Services This Project Runs

| Service | Port | Health Endpoint | Watchdog Script | Purpose |
|---------|------|-----------------|-----------------|---------|
| Example API | 8000 | http://localhost:8000/health | `scripts/watchdog_api.sh` | Main REST API |
| Example Worker | - | - | `scripts/watchdog_worker.sh` | Background job processor |

## External Dependencies

| Service | Required | Default | Purpose | Fallback if Missing |
|---------|----------|---------|---------|---------------------|
| PostgreSQL | Yes | localhost:5432 | Primary database | None - required |
| Redis | Optional | localhost:6379 | Caching/queues | Works without, slower |

## Startup Order

Start services in this order:

1. **External services** (database, cache)
   ```bash
   # If using Docker
   docker-compose up -d postgres redis
   ```

2. **API Server**
   ```bash
   ./scripts/watchdog_api.sh start
   ```

3. **Background Workers**
   ```bash
   ./scripts/watchdog_worker.sh start
   ```

## Quick Commands

```bash
# Start all services
./scripts/start_all.sh

# Stop all services
./scripts/stop_all.sh

# Check status of all services
./scripts/status.sh

# View logs
tail -f logs/*.log
```

## Service Details

### API Server

- **Start:** `./scripts/watchdog_api.sh start`
- **Stop:** `./scripts/watchdog_api.sh stop`
- **Status:** `./scripts/watchdog_api.sh status`
- **Health:** `curl http://localhost:8000/health`
- **Logs:** `logs/api.log`

### Background Worker

- **Start:** `./scripts/watchdog_worker.sh start`
- **Stop:** `./scripts/watchdog_worker.sh stop`
- **Status:** `./scripts/watchdog_worker.sh status`
- **Logs:** `logs/worker.log`

## Troubleshooting

### Service Won't Start

1. Check if port is already in use: `lsof -i :8000`
2. Check logs: `tail -50 logs/api.log`
3. Verify dependencies are running: `./scripts/status.sh`

### Service Keeps Crashing

1. Check watchdog log: `tail -f logs/api_watchdog.log`
2. Look for memory issues: `free -h`
3. Check disk space: `df -h`

---

*Last updated: YYYY-MM-DD*
