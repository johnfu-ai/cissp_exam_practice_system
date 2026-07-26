# Tier 2 #27: multi-stage build. The builder installs deps + builds the Next.js
# standalone output; the runtime image ships only the traced standalone server
# + static assets, runs as a non-root user, and drops the hardcoded npm mirror.

# ---- deps + build ----
FROM node:24-slim AS builder

WORKDIR /app

# Registry is configurable via build arg (default: official npm registry). The
# previous hardcoded registry.npmmirror.com is removed.
ARG NPM_REGISTRY=https://registry.npmjs.org
COPY package.json package-lock.json* ./
RUN npm config set registry "${NPM_REGISTRY}" \
 && npm config set fetch-retries 5 \
 && npm config set fetch-retry-mintimeout 20000 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 300000 \
 && for i in 1 2 3 4 5; do \
        npm ci --no-audit --no-fund && exit 0; \
        echo "npm ci attempt $i failed (network), retrying in 5s..."; \
        sleep 5; \
    done; exit 1

COPY . .
RUN npm run build

# ---- runtime ----
FROM node:24-slim

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN useradd --create-home --uid 1001 nextjs

# Next standalone build: the minimal self-contained server + static chunks.
# public/ is copied only if it exists in the repo (currently it doesn't, so the
# line is a no-op via a wildcard that won't fail the build if absent).
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# standalone server.js honors PORT + HOSTNAME env vars.
CMD ["node", "server.js"]
