# SaaS Skeleton Template

## Overview

A reusable Next.js SaaS starter with marketing pages, authenticated app shell, and a signed-in, rate-limited chat (`POST /api/v1/chat`).

## Features

- **Marketing Site**: Landing, pricing, FAQ, terms, privacy pages
- **App Shell**: Sidebar navigation, dashboard, job workflow
- **Chat**: SSE streaming components wired to the backend's authenticated, rate-limited `POST /api/v1/chat`
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
# Edit .env — frontend needs NEXT_PUBLIC_API_URL; the same root .env (compose's
# env_file for the api and worker) holds DATABASE_URL, REDIS_URL, JWT_SECRET (Pattern A)

# Start development
npm run dev
```

## Documentation

See `docs/QUICKSTART.md` for build instructions and local development, and `CLAUDE.md` for coding conventions.

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

The backend serves chat at `POST /api/v1/chat` (`server/src/<pkg>/chat.py`). Only a signed-in user
can spend the app's model key, and every request is rate-limited:

```tsx
import { ChatUI } from "@/components/chat";

export default function ChatPage() {
  return <ChatUI endpoint="/api/v1/chat" placeholder="Ask anything..." />;
}
```

`ChatUI` sends only `{ message }` with the session cookie and the `X-CSRF-Token` header, and renders
the `text_delta` / `done` / `error` SSE events it receives. On a 401 it refreshes the session once
through `/auth/refresh` and retries; a stream that ends without `done` or `error` shows "The reply
was cut off", and a finished reply with no text shows "The model returned an empty reply". The
model's instructions are the server constant `CHAT_SYSTEM_PROMPT`, never part of the request.

### Turning chat on

1. Set `OPENROUTER_API_KEY` (the spec's `secrets.from_env` lists it) and `OPENROUTER_MODEL` (in the
   root `.env`; it is not a secret, so it is not listed). Either
   one empty means chat answers a signed-in user's valid request with 503 (a signed-out caller still
   gets 401, a bad body 400 or 413).
2. Keep `shape.needs_cache: true` (the default), so `REDIS_URL` is set. Without Redis, chat answers 503.
3. Put the app's public URL in the origin allowlist web login already uses (`AUTH_ALLOWED_ORIGINS`,
   else `CORS_ORIGINS` plus `NEXT_PUBLIC_APP_URL`). A cookie-borne chat request from an origin outside it,
   or without the `X-CSRF-Token` header, is a 403; a bearer-token client skips both checks.
4. Set a USD `limit` on the OpenRouter key itself. That caps spend on OpenRouter's side whatever the
   app does.

The template ships no login page: chat needs one, through `/auth/login/web` or passwordless.

The relative `endpoint="/api/v1/chat"` relies on the same-host front the emitted compose sets up
(Traefik sends `/api` and `/auth` to the backend, everything else to Next). `next dev` alone on its
own port proxies neither, so a chat request there reaches Next and is a 404.

### Limits and cost

Up to four buckets must all pass, checked together before any is counted: the whole app
(`CHAT_RATE_APP`, default 1200 per hour), the tenant (`CHAT_RATE_TENANT`, 600; only for a user who
belongs to one), the user (`CHAT_RATE_USER`, 60) and the client IP (`CHAT_RATE_IP`, 120; IPv6 per
/64, an IPv6 address carrying an IPv4 one as that IPv4; only when the IP parses). A full bucket answers 429 with `Retry-After`. The windows are fixed,
each starting at its bucket's first request, so at the defaults the app produces at most
1200 × 1024 = 1,228,800 output tokens per window, and up to twice that in any one rolling hour that
spans two windows; multiply by your model's price to get the ceiling in money.

A message over `CHAT_MAX_MESSAGE_CHARS` (4000) is a 400, a body over `CHAT_MAX_BODY_BYTES` (64 KiB)
a 413, and a malformed `CHAT_*` value fails the app at start.

`CHAT_MAX_TOKENS` (default 1024) bounds each reply. On a reasoning model it covers the reasoning and
the visible reply together, so a small value can return an empty reply that stopped at the limit;
raise it there.

Anyone with an email address can sign up while passwordless auto-signup is on, and a bot that mints
users can fill the app bucket and refuse everyone until the hour ends. Set
`AUTH_PASSWORDLESS_AUTO_SIGNUP=false` when sign-up should not be open.

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

# Backend (the same root .env; compose's env_file hands it to the api and worker) — the IdP owns these:
#   DATABASE_URL=postgresql://…@postgres-main:5432/<db>
#   REDIS_URL=redis://redis-main:6379/<n>   (fabrik apply assigns the app its own DB, 1-15)
#   JWT_SECRET=<32+ char secret>
#   OPENROUTER_API_KEY=, OPENROUTER_MODEL=   chat (see "Turning chat on" above)
#   CHAT_RATE_*, CHAT_MAX_*, CHAT_UPSTREAM_READ_TIMEOUT   chat limits (see "Limits and cost")
#   TEST_REDIS_URL=   the chat tests' throwaway Redis DB (server/tests/test_chat.py only)

# App
NEXT_PUBLIC_APP_NAME=Your SaaS
NEXT_PUBLIC_APP_URL=http://localhost:3000

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
