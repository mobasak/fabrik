# [Project Name]

**Last Updated:** YYYY-MM-DD

> **Purpose:** PRIMARY ENTRY POINT — OVERVIEW, TECH STACK, REQUIREMENTS.

<!--
  README vs QUICKSTART — keep the boundary:
    README:     "What is this project? Why does it exist? What can it do?"
                Keep to 150–300 words. Link to QUICKSTART for setup.
    QUICKSTART: "How do I get it running in 5 minutes?" → commands + checks.
  If you find yourself pasting `cd / npm i / docker compose up` here,
  move it to docs/QUICKSTART.md.
-->

[One-line description]

**Type:** {python-api | node-api | saas-skeleton | chrome-extension | mobile-app | desktop-app | static-site}
**Port:** {PORT}

---

## Overview

<!-- 2–3 sentences: what this project does, who it's for, what problem it solves. -->

## Tech Stack

<!-- Replace with actual stack. Delete lines that don't apply. -->

- **Runtime:** Python 3.12 / Node 22
- **Framework:** FastAPI / Next.js / Hono
- **Database:** PostgreSQL (shared `postgres-main:5432`)
- **Cache:** Redis (`redis-main:6379`)
- **Deployment:** Docker Compose → VPS (`fabrik apply`)

## Requirements

- Docker + Docker Compose
- `.env` configured from `.env.example`

## Documentation

See [INDEX.md](INDEX.md) for master file index and documentation links.
