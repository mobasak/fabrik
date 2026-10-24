---
activation: glob
globs: ["**/docs/design-system.md", "**/docs/ui-design.md", "**/*.tsx", "**/*.jsx", "**/*.astro", "**/*.vue", "**/*.svelte", "**/src/*.html", "**/src/*/*.html", "**/src/*/*/*.html", "**/public/*.html", "**/public/*/*.html", "**/tailwind.config.*", "**/globals.css", "**/global.css", "**/custom.css", "**/tailwind.css", "**/theme.css", "**/src/styles/*.css"]
description: Web UI design routes to the frontend-design:frontend-design skill (operator ruling 2026-10-24) — when it is invoked, the brief that outranks it (operator rulings, the frozen ui-design.md and design-system.md with the template's structure), and its AI-generated clusters written out for readers without the skill.
trigger: glob
currency_pass: 2026-10-24
---
<!-- CONSUMER: coding agents designing, building or reviewing a WEB surface; /fabrik-ui-design, /fabrik-ui-design-review, /design-review, the fabrik-gui and design-review agents (each points here)
     GOAL: every web UI-design act goes through one skill, under one brief order, so the skill's taste never overrides a frozen contract
     AGENT USAGE: invoke `frontend-design:frontend-design` with the brief below; without the skill, apply the same brief and the clusters below, and say so -->

# Frontend design — the skill and its brief

## Designing what the brief leaves free

On a WEB surface — a SaaS frontend, a static or Docusaurus site, an extension's pages, an Electron or Tauri
renderer — every UI-design act invokes the **`frontend-design:frontend-design`** skill (the claude-plugins-official
plugin `frontend-design@claude-plugins-official`; operator ruling 2026-10-24, "use frontend design plugin for ui
designs in websites"). Never the older `example-skills:frontend-design`, which shares the bare name. The acts:

- designing what a new brand's kit leaves free in `/fabrik-ui-design` Phase 1 (the one memorable element, the
  copy's voice);
- laying out what each screen leaves free in `/fabrik-ui-design` Phase 5 (a marketing or landing hero's form,
  the one memorable element);
- building a screen — the skill's build and self-critique passes only, inside what the contract lists, since its
  plan pass is already frozen in the contract.

The visual critique in `/fabrik-ui-design-review` and `/design-review` applies the skill's critique as written out
below (its AI-generated clusters and generic treatments); a reviewer without the Skill tool needs nothing else.

Mobile surfaces are outside this rule; their packs stand.

**The brief always wins** — the skill's own rule ("the brief's own words always win"), made concrete. The brief
is, in order:

1. the operator's rulings;
2. the project's frozen `docs/ui-design.md`;
3. the project's `docs/design-system.md` (brand-identiy-creator tokens or a declared house identity) together
   with the structure it inherits from `design-system-template.md` and the surface pack (`saas/60-saas-ui.md`,
   `chrome-ext/70-chrome-ext.md`, `desktop-app/72-desktop.md`);
4. a project-local `context/style-guide.md` or `context/design-principles.md`, if present.

A pattern the template or the surface pack prescribes — the uppercase micro-label, the mono face for numeric
data, the KPI card, card hover lift, one card radius — is brief, never a free axis. Typography is a frozen row:
only the treatment of a hero or display moment, within the frozen families and scale, is free. The skill's token
plan restates the frozen tokens (in `/fabrik-ui-design` Phase 1, the brand kit's) and never mints a hex value. The subject, the audience and the primary job come
from the spec and `docs/ui-design.md`, which answer the skill's "confirm with the client" step: a run never stops
to confirm them. What stays free is what the brief does not settle: the hero's form, the layout concept of a
marketing or landing surface, the one memorable element, the copy.

## The AI-generated clusters (checked only on the free axes)

The skill names traits that AI-generated design clusters around. Written out here for readers without the skill
(the `design-review` agent, Windsurf, Kilo); paraphrased from the skill's § Process, which stays the source:

1. a warm cream background with a high-contrast serif display and a terracotta accent;
2. a near-black background with one bright acid-green or vermilion accent;
3. a broadsheet layout — hairline rules, zero radius, dense newspaper columns;
4. identical rounded cards with one radius, one soft grey shadow and gradient washes as decoration;
5. template chrome whatever the subject — a tracked-out all-caps eyebrow above every heading, meta strings joined
   with middle dots, `WORD — fragment` labels, a tinted near-black standing in for black, a monospace face for
   small data labels, an arrow appended to link and button text.

The skill also treats as generic: one accented word in a headline, numbered markers on content that is not a
sequence, and fade-and-slide entrances on every section. A review that finds one of these on a FREE axis reports
it, and the finding terminates like any other: FIXED (the choice changes) or REFUTED (the review cites the line of
the brief or the spec that makes the choice deliberate). It never closes by editing a frozen contract in place.
A frozen token, a pattern the template prescribes and an operator ruling are never findings.

## Without the skill

An agent that cannot invoke the skill applies the same brief order and the clusters above, and says in its report
that the skill was not available.
