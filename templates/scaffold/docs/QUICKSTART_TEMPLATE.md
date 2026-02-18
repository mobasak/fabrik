# Quick Start

Get [Project Name] running in 5 minutes.

## Prerequisites

- Python 3.11+
- pip

## Installation

```bash
# Navigate to project
cd /opt/<project>

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

```bash
# Copy environment template
cp .env.example .env
# Edit as needed
nano .env
```

Key settings:

```bash
# Application
PORT=8000
LOG_LEVEL=info

# Database (if needed)
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=project_dev
# DB_USER=postgres
# DB_PASSWORD=
```

## First Run

```bash
# Start the service
uvicorn src.<package_name>.main:app --reload --port 8000

# Check health
curl http://localhost:8000/health
```

Expected output:

```json
{
  "service": "project-name",
  "status": "ok",
  "dependencies": {
    "fastapi": "connected",
    "uvicorn": "connected",
    "pydantic": "connected"
  },
  "environment": "missing"
}
```

## Basic Usage

### Example 1: Health Check

```bash
curl http://localhost:8000/health
```

### Example 2: Root Endpoint

```bash
curl http://localhost:8000/
```

Expected output:

```json
{
  "message": "Welcome to project-name"
}
```

## Verify It Works

```bash
# Run tests
pytest tests/ -v

# Expected: All tests pass
```

## Next Steps

- [Configuration Guide](CONFIGURATION.md) - Full settings reference
- [Troubleshooting](TROUBLESHOOTING.md) - If something goes wrong
- [Development](../INDEX.md) - Full documentation index
