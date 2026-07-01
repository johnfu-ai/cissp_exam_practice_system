FROM node:24-slim

WORKDIR /app

COPY package.json package-lock.json* ./
# Use a mirror registry resilient to mid-stream ECONNRESET, and retry the
# whole install a few times — npm's internal fetch-retries don't always
# recover from a connection reset partway through a large download.
RUN npm config set registry https://registry.npmmirror.com \
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

EXPOSE 3000

CMD ["npm", "start"]
