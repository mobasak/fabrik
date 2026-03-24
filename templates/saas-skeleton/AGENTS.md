# SaaS Skeleton - Agent Briefing

> Instructions for AI coding agents (Windsurf Cascade, Kilo CLI, Traycer)

## Build & Test

```bash
npm install
npm run dev          # Start development server
npm run build        # Production build
npm run lint         # Lint check
```

## Run Locally

```bash
npm run dev
# Open http://localhost:3000
curl http://localhost:3000/api/health
```

## Docker

```bash
docker compose up -d
docker compose logs -f
```

## Kilo CLI Quick Reference

```bash
# Read-only analysis
kilo run "Analyze this Next.js project"

# Development
kilo run "Add new API endpoint for user profile"

# Planning (Traycer — preferred):
# Traycer-managed tasks: planning happens in Traycer Phases
# /yolo smart "Fix TypeScript errors and run build"
# /yolo phased "Add Stripe subscription integration"
```

## Project Structure

```
├── app/
│   ├── (marketing)/     # Public pages (landing, pricing, etc.)
│   ├── (app)/app/       # Authenticated pages (dashboard, etc.)
│   ├── api/             # API routes
│   └── layout.tsx       # Root layout
├── components/
│   ├── shell/           # AppShell
│   ├── common/          # Reusable UI
│   └── chat/            # ChatUI
├── lib/                 # Utilities and config
├── Dockerfile           # Production build
└── compose.yaml         # Coolify deployment
```

## Conventions

### Environment Variables

```typescript
// CORRECT - use relative URLs for same-origin API calls
const response = await fetch('/api/health');

// CORRECT - require env var for external APIs
const externalApiUrl = process.env.NEXT_PUBLIC_API_URL!;

// WRONG - hardcoded localhost
const apiUrl = 'http://localhost:3000';
```

### API Routes

```typescript
// app/api/example/route.ts
export async function GET() {
  return Response.json({ status: "ok" });
}
```

## Customization

1. **Branding**: Edit `lib/config/site.ts`
2. **Marketing**: Edit pages in `app/(marketing)/`
3. **App pages**: Edit pages in `app/(app)/app/`

## Security

- Never commit `.env` — Use `.env.example` as template
- API keys in environment variables only
- Supabase RLS policies for data access
