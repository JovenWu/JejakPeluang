# JejakPeluang

National catalogue of verified scholarships, internships, and competitions for Indonesian students. Every entry is reviewed by a human moderator and linked to its original source.

First slice: a read-only public catalogue — Next.js Bahasa Indonesia UI (`apps/web`), FastAPI + PostgreSQL backend (`services/backend`), shared OpenAPI types (`packages/contracts`), and a Playwright end-to-end flow (`tests/e2e`). Intake, uploads, AI matching, and production deployment are out of scope.

## Prerequisites

- Node.js 24
- pnpm 10 (`corepack enable` selects the pinned version)
- uv (Python 3.13)
- Docker with Compose v2

## Setup

```sh
pnpm install
cd services/backend && uv sync
```

For the local integration stack, copy `infra/.env.example` to `infra/.env` and fill in the pinned image digests and a disposable `TEST_DB_PASSWORD`. The compose stack fails to start if any variable is unset.

```sh
docker compose -f infra/compose.dev.yml up --build --wait
docker compose -f infra/compose.dev.yml exec api uv run alembic upgrade head
docker compose -f infra/compose.dev.yml exec api uv run python scripts/seed_e2e.py  # optional test fixture
```

Web: http://127.0.0.1:3000 — API: http://127.0.0.1:8000 (localhost-only; Postgres stays internal). Set `API_PORT`/`WEB_PORT` in `infra/.env` if those host ports are taken. Stop with `docker compose -f infra/compose.dev.yml down` (`-v` also drops the database volume).

Without Docker, point `DATABASE_URL` at any database (e.g. `sqlite+pysqlite:///./dev.db` for a quick look) and run:

```sh
cd services/backend && uv run alembic upgrade head && uv run uvicorn app.main:app
pnpm --filter @jejakpeluang/web dev   # API_INTERNAL_ORIGIN unset → rewrites fall back to http://localhost:8000
```

Regenerate the shared contract types after the API schema changes (`scripts/export_openapi.py` refreshes `packages/contracts/openapi.json`):

```sh
pnpm --filter @jejakpeluang/contracts generate
```

## Tests

```sh
cd services/backend && uv run pytest        # backend unit/API tests (SQLite)
pnpm --filter @jejakpeluang/web test        # web component tests
pnpm --filter @jejakpeluang/web lint        # eslint
pnpm --filter @jejakpeluang/web build       # production build
pnpm --filter @jejakpeluang/e2e exec playwright install chromium   # one-time
pnpm --filter @jejakpeluang/e2e test:e2e    # needs the compose stack up
```
