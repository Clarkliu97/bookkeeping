FROM node:22-alpine AS base

WORKDIR /app

FROM base AS deps

COPY package.json package-lock.json* ./
RUN npm ci

FROM deps AS development

COPY . .

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM deps AS builder

COPY . .
RUN npm run build

FROM base AS production

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

COPY package.json package-lock.json* ./
RUN npm ci --omit=dev
COPY next.config.mjs ./next.config.mjs
COPY --from=builder /app/.next ./.next

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
