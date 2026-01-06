---
activation: glob
globs: ["**/*.ts", "**/*.tsx"]
description: Next.js patterns, React components, API routes
---

# TypeScript Rules

**Activation:** Glob `**/*.ts`, `**/*.tsx`
**Purpose:** Next.js patterns, React components, API routes

---

## SaaS Projects (MANDATORY)

**Always start from the SaaS skeleton:**
```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

**Template includes:**
- Next.js 14 + TypeScript + Tailwind CSS
- Marketing pages (landing, pricing, FAQ)
- App pages (dashboard, settings)
- SSE streaming + ChatUI

---

## Environment Variables

```typescript
// CORRECT - runtime access
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const dbHost = process.env.DB_HOST || 'localhost';

// Server-side only (no NEXT_PUBLIC_ prefix)
const secretKey = process.env.SECRET_KEY;
```

---

## Component Patterns

```tsx
// Functional components with TypeScript
interface Props {
  title: string;
  count?: number;
}

export function Card({ title, count = 0 }: Props) {
  return (
    <div className="p-4 rounded-lg border">
      <h2>{title}</h2>
      <span>{count}</span>
    </div>
  );
}
```

---

## API Routes (App Router)

```typescript
// app/api/items/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const items = await fetchItems();
  return NextResponse.json(items);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const item = await createItem(body);
  return NextResponse.json(item, { status: 201 });
}
```

---

## Styling

- Use Tailwind CSS for all styling
- Use shadcn/ui components
- Use Lucide icons

```tsx
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

<Button variant="outline" size="sm">
  <Plus className="w-4 h-4 mr-2" />
  Add Item
</Button>
```

---

## Port Range

Frontend apps: **3000-3099**

```bash
npm run dev -- --port 3000
```

---

## Quality

```bash
npm run lint          # ESLint
npm run type-check    # TypeScript
npm run build         # Production build
```
