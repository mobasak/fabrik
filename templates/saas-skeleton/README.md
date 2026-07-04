# SaaS Skeleton Template

## Overview

A reusable Next.js SaaS starter with marketing pages, authenticated app shell, and AI chat integration.

## Features

- **Marketing Site**: Landing, pricing, FAQ, terms, privacy pages
- **App Shell**: Sidebar navigation, dashboard, job workflow
- **Chat UI**: SSE streaming component for AI chat integration
- **Self-hosted auth (Pattern A)**: the FastAPI backend (`server/`) is the IdP — issues its own JWTs via the vendored `fastapi_user_auth` (Argon2, refresh rotation, jti denylist, tenant RLS) on `postgres-main` + `redis-main`

## Quick Start

```bash
# Copy template to new project
cp -r templates/saas-skeleton /opt/my-saas

# Install dependencies
cd /opt/my-saas
npm install

# Configure environment
cp .env.example .env
# Edit .env — frontend needs NEXT_PUBLIC_API_URL + OpenRouter; the backend
# (server/.env) holds DATABASE_URL, REDIS_URL, JWT_SECRET (Pattern A)

# Start development
npm run dev
```

## Documentation

See `AGENTS.md` for build instructions, local development, and coding conventions.

## Project Structure

```
├── Dockerfile            # Production Docker build
├── compose.yaml          # SSH + Docker Compose deployment config (`fabrik apply`)
├── app/
│   ├── (marketing)/      # Public pages
│   │   ├── page.tsx      # Landing
│   │   ├── pricing/      # Pricing
│   │   ├── faq/          # FAQ
│   │   ├── terms/        # Terms
│   │   └── privacy/      # Privacy
│   ├── (app)/app/        # Authenticated pages
│   │   ├── page.tsx      # Dashboard
│   │   ├── new/          # Create job
│   │   ├── items/        # List jobs
│   │   ├── items/[id]/   # Job detail
│   │   └── settings/     # Settings
│   ├── api/
│   │   ├── chat/         # SSE streaming endpoint
│   │   └── health/       # Health check endpoint
│   └── layout.tsx        # Root layout
├── components/
│   ├── shell/            # AppShell
│   ├── common/           # PageHeader, SectionCard, EmptyState
│   └── chat/             # ChatUI, SSEStream
├── lib/
│   ├── config/           # Site config
│   └── utils.ts          # Utilities
└── types/                # TypeScript types
```

## AI Chat Integration

### Chat UI Component

The template includes a pre-built chat component that streams AI responses:

```tsx
import { ChatUI } from "@/components/chat";

export default function ChatPage() {
  return (
    <ChatUI
      endpoint="/api/chat"
      placeholder="Ask anything..."
      systemPrompt="You are a helpful assistant."
    />
  );
}
```

The `/api/chat` endpoint streams responses via SSE, backed by the **OpenRouter API** (`openrouter.ai/api/v1` — one key, every provider; no vendor SDK). Set `OPENROUTER_API_KEY` and optionally `OPENROUTER_MODEL` (default `anthropic/claude-sonnet-4.6`; pick any slug from <https://openrouter.ai/models>). The route re-emits `text_delta` / `done` / `error` events the `ChatUI` consumes, and returns 503 if `OPENROUTER_API_KEY` is unset.

### Kilo CLI for Development

```bash
# Analyze codebase
kilo run "Analyze this project structure"

# Add features
kilo run "Add user profile page"

# Traycer (preferred for complex tasks)
# /yolo smart "Install deps and fix TypeScript errors"
# /yolo phased "Add Paddle subscription integration"
```

## Documentation Site

`fabrik scaffold --type saas-skeleton` auto-vendors the canonical docs template
from `fabrik-lib/docs-site` into **`docs-site/`** — a self-contained Docusaurus
site with Ocoron design tokens, Scalar API reference, Pagefind search, and
legal page templates (terms / privacy / cookies, GDPR/KVKK-compliant). Per
`.windsurf/rules/saas/88-saas-launch-checklist.md`, every SaaS must ship a docs
site — this is it; **don't build one from scratch**.

Before its first build (it's a separate npm project):

```bash
cd docs-site
# Download Space Grotesk, Inter, JetBrains Mono .woff2 into static/fonts/
# (the template doesn't ship 3rd-party font binaries — see docs-site/README.md)
npm install && npm run build      # or `npm start` for dev
```

Customize `docs-site/docusaurus.config.js` (title, url, Scalar spec URL) and
deploy it as its own service (its `nginx.conf` serves the static build). See
`docs-site/README.md` and `.windsurf/rules/core/42-docusaurus.md`.

## Environment Variables

```bash
# Frontend (Pattern A: no DB/auth secrets — just the backend API base URL)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Backend (server/.env) — the IdP owns these:
#   DATABASE_URL=postgresql://…@postgres-main:5432/<db>
#   REDIS_URL=redis://redis-main:6379/0
#   JWT_SECRET=<32+ char secret>

# App
NEXT_PUBLIC_APP_NAME=Your SaaS
NEXT_PUBLIC_APP_URL=http://localhost:3000

# AI chat (OpenRouter — required for /api/chat)
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=anthropic/claude-sonnet-4.6
```

## Customization

1. **Branding**: Edit `lib/config/site.ts`
2. **Navigation**: Edit `navConfig` in `lib/config/site.ts`
3. **Colors**: Edit CSS variables in `app/globals.css`
4. **Features**: Add routes in `app/(app)/app/`

## Deployment

### Local Docker Test

```bash
docker build -t my-saas .
docker run -p 3000:3000 my-saas
```

### VPS Deployment (`fabrik apply`)

The template includes `Dockerfile` and `compose.yaml` ready for SSH + Docker Compose deployment:

1. Push to Git repository
2. Register the service spec under `specs/services/`
3. Run `fabrik apply` — it SSHes to the VPS and runs Docker Compose
4. Set environment variables in the service `.env` (merged on deploy)
5. Traefik routes the container once the healthcheck passes

### Health Check

The `/api/health` endpoint returns service status:

```bash
curl http://localhost:3000/api/health
# {"status":"ok","timestamp":"...","uptime":123.45,"environment":"production"}
```

## License

MIT
