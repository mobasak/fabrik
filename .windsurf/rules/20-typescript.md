---
activation: glob
globs: ["**/*.ts", "**/*.tsx"]
description: Next.js patterns, React components, API routes
trigger: glob
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

## Visual Design Workflow (SaaS/Web/Mobile/Extension/Any Other)

For UI-heavy projects, use this iterative design-to-code workflow:

### Step 1: Provide Design Reference
- Screenshot of mockup/Figma design
- Existing site/app you want to replicate
- Detailed written description of desired UI

### Step 2: AI Generates Code
- Cascade/Kilo generates component code from description or screenshot
- Uses Tailwind CSS + shadcn/ui components automatically
- Follows TypeScript best practices (type-safe props, proper imports)

### Step 3: Iterate Until Perfect
- Review generated code in browser
- Request adjustments: "Make card shadow stronger", "Use primary color for CTA button"
- Refine spacing, colors, typography until matches design

**Best Practices:**
- Start with complete page mockups, not individual components
- Provide color palette (`primary: #3B82F6`) and spacing guidelines upfront
- Use existing shadcn/ui components when possible (reduces custom code)
- For Chrome extensions: Include popup dimensions in design reference
- For mobile: Specify target devices (iOS, Android, or both)

**Example Prompt:**
```
Create a pricing page with 3 tiers (Free, Pro, Enterprise).
Design: Modern SaaS style, use Tailwind's blue-600 for primary color.
Each card should have: tier name, price, feature list (checkmarks), CTA button.
Make the Pro tier highlighted with a "Popular" badge.
```
