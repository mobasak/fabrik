# WordPress - Agent Briefing

> Instructions for AI coding agents (droid exec, Cursor, Windsurf, etc.)

## Run Locally

```bash
docker compose up -d
docker compose logs -f
# Open http://localhost:8080
```

## droid exec Quick Reference

```bash
droid exec "Analyze this WordPress setup"
droid exec --auto medium "Add custom post type"
droid exec --use-spec "Create child theme"
```

## Docker Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Logs
docker compose logs -f wordpress

# Shell access
docker compose exec wordpress bash
```

## Conventions

- Use child themes for customization
- Environment variables for wp-config
- Volumes for persistent data

## Project Structure

```
├── compose.yaml           # Docker Compose config
├── wp-content/
│   ├── themes/           # Custom themes
│   ├── plugins/          # Custom plugins
│   └── uploads/          # Media uploads
└── .env                  # Environment config
```

## Security

- Never commit wp-config.php with credentials
- Use strong admin passwords (32 char CSPRNG)
- Keep WordPress and plugins updated
- Use Traefik for HTTPS
