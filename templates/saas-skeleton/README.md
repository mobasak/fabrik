# SaaS Skeleton Template

## Overview

A reusable Next.js SaaS starter with marketing pages, authenticated app shell, and AI chat integration.

## Features

- **Marketing Site**: Landing, pricing, FAQ, terms, privacy pages
- **App Shell**: Sidebar navigation, dashboard, job workflow
- **Chat UI**: SSE streaming component for AI chat integration
- **Supabase Ready**: Auth and database integration

## Quick Start

```bash
# Copy template to new project
cp -r templates/saas-skeleton /opt/my-saas

# Install dependencies
cd /opt/my-saas
npm install

# Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials

# Start development
npm run dev
```

## Documentation

See `AGENTS.md` for build instructions, local development, and coding conventions.

## Project Structure

```
├── Dockerfile            # Production Docker build
├── compose.yaml          # Coolify deployment config
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

The `/api/chat` endpoint streams responses via SSE.

### Kilo CLI for Development

```bash
# Analyze codebase
kilo run "Analyze this project structure"

# Add features
kilo run "Add user profile page"

# Traycer (preferred for complex tasks)
# /yolo smart "Install deps and fix TypeScript errors"
# /yolo phased "Add Stripe subscription integration"
```

## Environment Variables

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

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

### Coolify Deployment

The template includes `Dockerfile` and `compose.yaml` ready for Coolify:

1. Push to Git repository
2. Create new service in Coolify
3. Select Docker Compose deployment
4. Set environment variables in Coolify dashboard
5. Deploy

### Health Check

The `/api/health` endpoint returns service status:

```bash
curl http://localhost:3000/api/health
# {"status":"ok","timestamp":"...","uptime":123.45,"environment":"production"}
```

## License

MIT
