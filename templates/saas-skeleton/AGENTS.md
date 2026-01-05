# SaaS Skeleton - Agent Briefing

> Instructions for AI coding agents (droid exec, Cursor, Windsurf, etc.)

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

## droid exec Quick Reference

```bash
# Read-only analysis
droid exec "Analyze this Next.js project"

# Development
droid exec --auto medium "Add new API endpoint for user profile"

# Full autonomy
droid exec --auto high "Fix TypeScript errors and run build"

# Spec mode for features
droid exec --use-spec "Add Stripe subscription integration"
```

### Key Flags

| Flag | Purpose |
|------|---------|
| `--auto low/medium/high` | Autonomy level |
| `--use-spec` | Plan before code |
| `-m <model>` | Model selection |
| `-o stream-json` | Real-time output |

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
│   └── chat/            # ChatUI for droid exec
├── lib/                 # Utilities and config
├── Dockerfile           # Production build
└── compose.yaml         # Coolify deployment
```

## Conventions

### Environment Variables

```typescript
// CORRECT
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000';

// WRONG - hardcoded
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
