# Fabrik SaaS Scaffold Skill

**MANDATORY:** When the user asks to create ANY SaaS application, web app, dashboard, or subscription service, you MUST use this skill to scaffold from Fabrik's SaaS skeleton template. Do NOT create from scratch.

## Triggers (Auto-Invoke)

**Primary triggers** (always use template):
- "SaaS"
- "web app"
- "dashboard"
- "subscription app"
- "create an app"
- "new project" + (web/frontend/UI)

**Secondary triggers** (likely needs template):
- "landing page"
- "pricing page"
- "user settings"
- "job workflow"
- "chat UI"
- "streaming UI"

## Template Location

`/opt/fabrik/templates/saas-skeleton/`

## Steps

1. **Copy the template** to the target project directory:
   ```bash
   cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
   ```

2. **Customize site config** in `lib/config/site.ts`:
   - Update `name` to the project name
   - Update `description` to match the use case
   - Customize `navConfig` for the specific app

3. **Create `.env`** from `.env.example`:
   - Set `NEXT_PUBLIC_APP_NAME`
   - Set Supabase credentials if using Supabase
   - Set `DROID_MODEL_ID` if using AI features

4. **Customize pages**:
   - Update landing page copy in `app/(marketing)/page.tsx`
   - Update pricing tiers in `app/(marketing)/pricing/page.tsx`
   - Modify job workflow in `app/(app)/app/new/page.tsx`

5. **Add business logic**:
   - Create API routes in `app/api/`
   - Add database models/schemas
   - Implement job processing

## Included Components

| Component | Location | Purpose |
|-----------|----------|---------|
| AppShell | `components/shell/` | Sidebar + navigation |
| PageHeader | `components/common/` | Page titles + actions |
| SectionCard | `components/common/` | Content containers |
| EmptyState | `components/common/` | Empty data states |
| ChatUI | `components/chat/` | AI chat interface |
| SSEStream | `components/chat/` | Streaming hook |

## Included Pages

### Marketing
- `/` - Landing page
- `/pricing` - Pricing tiers
- `/faq` - FAQ
- `/terms` - Terms of service
- `/privacy` - Privacy policy

### App (Authenticated)
- `/app` - Dashboard
- `/app/new` - Create job
- `/app/items` - List jobs
- `/app/items/[id]` - Job detail
- `/app/settings` - User settings

## Job Workflow Pattern

The template implements a generic job-based workflow:

```
DRAFT → QUEUED → RUNNING → SUCCEEDED | FAILED | CANCELED
```

This pattern works for:
- File processing (transcription, conversion, analysis)
- AI tasks (generation, summarization)
- Data pipelines (scraping, ETL)
- Any async workflow

## AI Integration

The template includes droid exec integration via SSE:

1. **API Route** (`app/api/chat/route.ts`):
   - Spawns `droid exec --output-format debug`
   - Streams responses via Server-Sent Events

2. **ChatUI Component** (`components/chat/ChatUI.tsx`):
   - Consumes SSE stream
   - Shows tool call indicators
   - Handles message state

## Environment Variables

```bash
# Required
NEXT_PUBLIC_APP_NAME=Your App Name

# Supabase (if using)
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=

# Droid (for AI features)
DROID_MODEL_ID=gemini-3-flash-preview
DROID_REASONING=low
```

## Deployment

Deploy to Coolify via Docker Compose. The template is designed to work with:
- VPS with droid exec installed on host
- Apps call droid via subprocess
- SSE streaming for real-time feedback

See `droid-exec-usage.md` §25-26 for full deployment patterns.
