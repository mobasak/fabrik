# SaaS Alternative GUI Stack (OpenRouter-inspired)

**Reference:** OpenRouter's production frontend (May 2026). Adapted to Fabrik stack. (Deploy references updated 2026-06-16.)

> **Note:** This stack deploys via `fabrik apply` (SSH + Docker Compose to the
> VPS; see `orchestrator/deployer_ssh.py`), not Coolify. Coolify was
> decommissioned 2026-05-30; the only surviving `coolify` reference is the
> legacy Docker-network name. The Docker images, runtime, and Traefik routing
> are identical to the Coolify era — only the orchestrator changed. The Fabrik
> fleet is 3 hosts; target a specific one with `fabrik apply --target-vps`.

---

## Stack Mapping

| OpenRouter uses | Fabrik equivalent | Notes |
|---|---|---|
| Next.js (App Router) on Vercel | **Next.js (App Router) on Fabrik VPS** | Same framework, self-hosted via Docker (deployed with `fabrik apply` — SSH + Docker Compose). No Vercel dependency. |
| Inter + Geist Mono via `next/font` | **Space Grotesk (headings) + Inter (body) + JetBrains Mono (code/data)** via `next/font` | Per Ocoron Design System. Geist Mono replaced by JetBrains Mono (our standard). |
| Tailwind CSS + HSL custom properties | **Tailwind CSS + Ocoron design tokens** (CSS custom properties) | Same approach. Our tokens: `--color-accent`, `--surface-0..3`, `--text-primary/body/muted`. |
| Radix UI + custom components (shadcn/ui-like) | **shadcn/ui** (built on Radix UI primitives) | Same thing — shadcn/ui IS Radix primitives + Tailwind styling. Already in our saas-skeleton scaffold. |
| Clerk (auth) | **Supabase Auth** (Pattern B) | Managed auth, same DX. Supabase is free-tier-friendly, Clerk is not. |
| Google Analytics + Datadog RUM + Vercel Speed Insights | **Umami** (self-hosted analytics) + **Sentry** (error tracking + performance) | No vendor analytics. Umami for traffic, Sentry for errors + Web Vitals. Both self-hosted on the Fabrik VPS. |
| next-themes (ThemeProvider) | **next-themes** (same) | Identical. Dark default, light toggle, OS preference, localStorage persistence. |
| Lucide icons | **Lucide** (same) | Already our standard per Ocoron Design System. |
| cmdk (command palette) | **cmdk** (same) | Already specified in Ocoron Design System § Search and Command Palette. |
| Turbopack | **Turbopack** (same) | Enabled in `next.config.ts` — `experimental: { turbo: {} }`. Works with Fabrik VPS Docker builds. |

---

## What We Keep Identical

- **Next.js App Router** — same routing, layouts, server components, streaming
- **Tailwind CSS** — same utility-first approach with design tokens as CSS custom properties
- **shadcn/ui** (Radix UI primitives) — same component library, same accessibility
- **Lucide** — same icon library
- **cmdk** — same command palette (`Cmd+K`)
- **next-themes** — same dark/light switching mechanism
- **`next/font`** — same font loading (self-hosted, no external CDN)
- **Turbopack** — same dev server performance

## What We Swap

| They use | We use | Why |
|---|---|---|
| Vercel hosting | **Fabrik VPS** (`fabrik apply`) | $3/mo vs $20+/mo. Same Docker builds. No vendor lock-in. |
| Clerk auth | **Supabase Auth** | Free tier, managed, RLS integration, mobile SDK. |
| Google Analytics | **Umami** (self-hosted) | Privacy-first, no cookie consent needed, GDPR-compliant by default. |
| Datadog RUM | **Sentry** (browser SDK) | Error tracking + performance monitoring. Already deployed as GlitchTip on VPS. |
| Vercel Speed Insights | **Sentry Web Vitals** or manual CWV reporting | Sentry captures LCP/FID/CLS automatically. |
| Geist Mono | **JetBrains Mono** | Our design system standard for code/data. |

---

## Implementation Notes

### Dockerfile (Next.js on Fabrik VPS)

```dockerfile
FROM node:22-bookworm-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

### next.config.ts

```typescript
import type { NextConfig } from 'next';

const config: NextConfig = {
  output: 'standalone',  // Required for Docker deployment
  experimental: {
    turbo: {},  // Turbopack for dev
  },
};

export default config;
```

### Theme Setup (next-themes + Ocoron tokens)

```typescript
// app/layout.tsx
import { ThemeProvider } from 'next-themes';
import { Inter, Space_Grotesk, JetBrains_Mono } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], variable: '--font-body' });
const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-heading' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export default function RootLayout({ children }) {
  return (
    <html suppressHydrationWarning>
      <body className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} font-sans`}>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

### Command Palette (cmdk)

```bash
npm install cmdk
```

Already specified in `ocoron-design-system.md` § Search and Command Palette — 560px centered modal, `Cmd+K` / `Ctrl+K`, fuzzy search, categories (Recent, Navigation, Records, Commands, Ask AI).

---

## When to Use This Stack

This is the **default SaaS frontend** for all `saas-skeleton` projects. The OpenRouter example validates it's production-grade at scale. No alternative needed unless:

- Marketing-only site → use `static-site` scaffold (simpler, no App Router needed)
- Documentation → use `docusaurus` scaffold
- Admin-only dashboard with no public users → still this stack, but skip Umami analytics

---

## Cost Comparison

| | OpenRouter (Vercel + Clerk + Datadog) | Fabrik (VPS + Supabase + Sentry) |
|---|---|---|
| Hosting | $20+/mo (Vercel Pro) | $3/mo (VPS share) |
| Auth | $25+/mo (Clerk Pro) | $0 (Supabase free tier) |
| Analytics | $0 (GA free) + $31+/mo (Datadog) | $0 (Umami self-hosted) |
| Error tracking | Included in Datadog | $0 (GlitchTip self-hosted) |
| **Total** | **$76+/mo** | **$3/mo** |

Same DX. Same component library. Same user experience. 96% cheaper.
