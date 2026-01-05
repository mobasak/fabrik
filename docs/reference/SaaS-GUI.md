## IMPLEMENTED ✅

**Template location:** `templates/saas-skeleton/`
**Droid skill:** `.factory/skills/fabrik-saas-scaffold.md`

---

## Overview
A reusable “SaaS GUI skeleton” you can copy for future projects that includes:
- Marketing site: landing + pricing + FAQ + legal pages
- App: authenticated layout + dashboard + settings
- Common UI: navigation, tables, forms, empty/loading/error states, toasts, modal, command palette (optional)
- “Job-based workflow” pages (upload → processing → results) without audio playback/piano roll
## Recommended stack (web-only, fast, reusable)
- **Next.js (App Router) + TypeScript**
- **Tailwind CSS**
- **shadcn/ui** (Radix primitives) for consistent components
- **React Hook Form + Zod** for forms/validation
- **TanStack Query** (or server actions only) for data fetching + caching
- **Auth**: NextAuth/Auth.js or Clerk (choose one per project)
- **Billing**: Stripe (stub interfaces in skeleton so you can plug later)
- **DB**: Postgres + Prisma (or Drizzle). Even if you swap later, keep repository interfaces stable.
## Information architecture (copy-paste for most SaaS)
### Public (marketing)
- `/` Landing (hero + primary CTA)
- `/pricing`
- `/faq`
- `/docs` (optional)
- `/privacy`, `/terms`
### App (authenticated)
- `/app` Dashboard (KPIs + recent items)
- `/app/new` Create/Upload (your “input” page)
- `/app/items` List (table + filters)
- `/app/items/[id]` Result detail (status + outputs)
- `/app/settings` Profile, Team, API keys, Billing
- `/app/admin` (optional)
This mirrors the “simple workflow” feel you liked: one prominent card to start, clear status, then results.
## Layout and components you should standardize once
### Layout primitives (don’t skip)
- `AppShell` (sidebar + topbar)
- `PageHeader` (title, description, actions)
- `SectionCard` (consistent padding/borders)
- `EmptyState` (icon, title, description, CTA)
- `StateBlocks`: `LoadingState`, `ErrorState`, `NoDataState`
- `ConfirmDialog`, `Modal`
- `Toast` notifications
- `DataTable` wrapper (sorting, pagination, empty state)
- `FormField` wrapper (label, hint, error)
### Styling rules (keeps everything “clean”)
- 1 spacing system: `p-6`, `gap-4`, `rounded-2xl`, `shadow-sm`
- 2 typography sizes: `text-2xl` for page titles, `text-sm text-muted-foreground` for help text
- 1 primary CTA per page
## Job-based workflow (your “upload → results” without playback)
Use a generic “job” model for many SaaS products (transcription, scraping, analysis, generation, conversions):
**States**
- `DRAFT` → `QUEUED` → `RUNNING` → `SUCCEEDED` | `FAILED` | `CANCELED`
**Pages**
- `/app/new`: creates job, uploads file, starts processing
- `/app/items/[id]`: shows progress + outputs + download buttons
**UI pattern**
- Big card input on `/app/new`
- Stepper/progress block on detail page
- Outputs in cards: “Summary”, “Files”, “Logs”, “Metadata”
- Export buttons always right-aligned in `PageHeader` actions
## Repo skeleton (recommended structure)
```
app/
  (marketing)/
    page.tsx
    pricing/page.tsx
    faq/page.tsx
    terms/page.tsx
    privacy/page.tsx
  (app)/
    app/layout.tsx        // AppShell
    app/page.tsx          // Dashboard
    app/new/page.tsx      // Create job
    app/items/page.tsx    // List
    app/items/[id]/page.tsx // Detail
    app/settings/page.tsx
components/
  shell/ (AppShell, Sidebar, Topbar)
  ui/ (shadcn components)
  common/ (PageHeader, SectionCard, EmptyState, DataTable, StateBlocks)
  forms/ (FormField wrappers)
lib/
  api/ (client wrappers)
  auth/
  db/
  jobs/ (job service interface + adapters)
  config/ (site config, nav config)
types/
  job.ts
```
## Minimal working “GUI skeleton” pieces (drop-in)
### 1) AppShell layout
```tsx
// app/(app)/app/layout.tsx
import type { ReactNode } from "react";
import Link from "next/link";
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl px-4 py-6">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[240px_1fr]">
          <aside className="rounded-2xl border p-4">
            <div className="text-sm font-semibold">Your SaaS</div>
            <nav className="mt-4 space-y-1 text-sm">
              <Link className="block rounded-lg px-3 py-2 hover:bg-muted" href="/app">Dashboard</Link>
              <Link className="block rounded-lg px-3 py-2 hover:bg-muted" href="/app/new">New</Link>
              <Link className="block rounded-lg px-3 py-2 hover:bg-muted" href="/app/items">Items</Link>
              <Link className="block rounded-lg px-3 py-2 hover:bg-muted" href="/app/settings">Settings</Link>
            </nav>
          </aside>
          <main className="rounded-2xl border p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
```
### 2) PageHeader + SectionCard
```tsx
// components/common/PageHeader.tsx
import type { ReactNode } from "react";
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex gap-2">{actions}</div> : null}
    </div>
  );
}
// components/common/SectionCard.tsx
import type { ReactNode } from "react";
export function SectionCard({ children }: { children: ReactNode }) {
  return <div className="rounded-2xl border p-6 shadow-sm">{children}</div>;
}
```
### 3) “New job” input card (generic)
```tsx
// app/(app)/app/new/page.tsx
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
export default function NewJobPage() {
  return (
    <div>
      <PageHeader
        title="Create"
        description="Upload an input and start a new job."
        actions={<button className="rounded-lg border px-3 py-2 text-sm hover:bg-muted">Help</button>}
      />
      <SectionCard>
        <div className="space-y-4">
          <div className="text-sm font-medium">Input</div>
          <div className="rounded-xl border border-dashed p-6 text-center">
            <div className="text-sm text-muted-foreground">Drag & drop or select a file</div>
            <div className="mt-3">
              <input type="file" className="text-sm" />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1">
              <div className="text-sm font-medium">Option A</div>
              <input className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="e.g., language" />
            </label>
            <label className="space-y-1">
              <div className="text-sm font-medium">Option B</div>
              <input className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="e.g., model" />
            </label>
          </div>
          <button className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            Start
          </button>
          <p className="text-xs text-muted-foreground">
            Tip: keep this page identical across projects; only swap labels/options.
          </p>
        </div>
      </SectionCard>
    </div>
  );
}
```
### 4) Job detail page (status + outputs)
```tsx
// app/(app)/app/items/[id]/page.tsx
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
const mock = {
  id: "job_123",
  status: "RUNNING" as const,
  progress: 42,
  outputs: [{ name: "result.json", kind: "file" }, { name: "report.pdf", kind: "file" }],
};
export default function ItemDetailPage() {
  const job = mock;
  return (
    <div>
      <PageHeader
        title={`Job ${job.id}`}
        description={`Status: ${job.status}`}
        actions={
          <>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-muted">Cancel</button>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-muted">Refresh</button>
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard>
          <div className="text-sm font-medium">Progress</div>
          <div className="mt-3 h-2 w-full rounded-full bg-muted">
            <div className="h-2 rounded-full bg-primary" style={{ width: `${job.progress}%` }} />
          </div>
          <div className="mt-2 text-xs text-muted-foreground">{job.progress}%</div>
        </SectionCard>
        <div className="lg:col-span-2">
          <SectionCard>
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium">Outputs</div>
              <button className="rounded-lg border px-3 py-2 text-sm hover:bg-muted">Download all</button>
            </div>
            <div className="mt-4 space-y-2">
              {job.outputs.map((o) => (
                <div key={o.name} className="flex items-center justify-between rounded-xl border p-3">
                  <div className="text-sm">{o.name}</div>
                  <button className="rounded-lg border px-3 py-2 text-sm hover:bg-muted">Download</button>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
```
## “Better than reference” by default (for your future SaaS)
Add these once to the skeleton and reuse everywhere:
- **Global search / command palette** (navigate + create new + open recent items)
- **Consistent empty states** (“No items yet” + “Create” CTA)
- **Inline onboarding** (checklist card on dashboard until user completes first job)
- **Activity log** per job (timestamps, durations, errors)
- **Feature flags** (turn features on/off per SaaS)
## Implementation order (fastest path)
1. Set up Next.js + Tailwind + shadcn/ui base theme
2. Build `AppShell`, `PageHeader`, `SectionCard`, `EmptyState`
3. Marketing pages `/`, `/pricing` (static)
4. App pages: `/app/new`, `/app/items`, `/app/items/[id]` with mock data
5. Plug auth + basic “jobs API” interface (even if backend is stubbed)
6. Replace mock with real data source
## If you want, I can produce a complete “starter repo blueprint” next
If you share:
- preferred auth choice (NextAuth vs Clerk)
- preferred DB (Prisma vs Drizzle vs none initially)
- whether you want team/multi-tenant from day 1
    I will return a single opinionated folder tree + exact packages + minimal schemas + route handlers, keeping the GUI identical across projects.
