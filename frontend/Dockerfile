# syntax=docker/dockerfile:1.7
# Multi-stage build for the Stockquare frontend.
# Stages:
#   1. deps    — install production + build dependencies via pnpm
#   2. builder — compile the Next.js app with standalone output
#   3. runner  — minimal runtime image that serves the standalone bundle

# ---------- Stage 1: deps ----------
FROM node:22-alpine AS deps

# libc6-compat keeps some native dependencies happy on Alpine.
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Enable pnpm via corepack (ships with Node 20+).
RUN corepack enable

# Only copy the files needed to resolve dependencies so the layer cache
# stays warm across unrelated source changes. pnpm-workspace.yaml carries
# the `allowBuilds` approvals for sharp / unrs-resolver native postinstalls.
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./

RUN pnpm install --frozen-lockfile


# ---------- Stage 2: builder ----------
FROM node:22-alpine AS builder

WORKDIR /app

RUN corepack enable

# Build-time public API base URL. Overridable via `docker build --build-arg`.
# NEXT_PUBLIC_* variables are inlined at build time, so they must be present here.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

# Always build with mocks disabled for production images.
ENV NEXT_PUBLIC_USE_MOCK=false
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN pnpm build


# ---------- Stage 3: runner ----------
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Run as a non-root user.
RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

# Next.js standalone output bundles only the files the server needs.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
