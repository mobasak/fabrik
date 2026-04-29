# Build stage
FROM node:22-bookworm-slim AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM node:22-bookworm-slim AS runner

WORKDIR /app

# B24: install curl for compose-level healthcheck. The scaffold's
# `_write_canonical_compose` (scaffold.py::_write_canonical_compose) emits a
# compose `healthcheck:` block that uses `curl -f`, which OVERRIDES this
# Dockerfile's HEALTHCHECK at runtime. node:22-bookworm-slim has no curl by
# default, so without this apt-get the container is `exited:unhealthy` within
# 30s of startup and Coolify rolls the deploy back. Other scaffold templates
# (node-api, file-api, file-worker, docusaurus) already do this; saas-skeleton
# was the lone gap, surfaced by the proof-run harness on 2026-04-28.
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Set ownership
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

CMD ["node", "server.js"]
