ARG NODE_IMAGE
FROM ${NODE_IMAGE}
WORKDIR /workspace
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/package.json packages/contracts/package.json
COPY packages/contracts/openapi.json packages/contracts/openapi.json
COPY packages/contracts/src/ packages/contracts/src/
COPY tests/e2e/package.json tests/e2e/package.json
RUN pnpm install --filter @jejakpeluang/web... --frozen-lockfile
ARG API_INTERNAL_ORIGIN=http://api:8000
ENV API_INTERNAL_ORIGIN=${API_INTERNAL_ORIGIN}
COPY apps/web/ apps/web/
RUN pnpm --filter @jejakpeluang/web build
CMD ["pnpm", "--filter", "@jejakpeluang/web", "start"]
