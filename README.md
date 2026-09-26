# JejakPeluang

National catalogue of verified scholarships, internships, and competitions for Indonesian students. Every entry is reviewed by a human moderator and linked to its original source.

Public catalogue + controlled intake — Next.js Bahasa Indonesia UI (`apps/web`), FastAPI + PostgreSQL backend (`services/backend`), shared OpenAPI types (`packages/contracts`), and a Playwright end-to-end flow (`tests/e2e`). Guest submissions and uploads feed an invite-only moderator queue (see Intake & moderation below); AI matching and production deployment remain out of scope.

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

## Intake & moderation (backend)

Environment variables the API reads (all ship with dev-only defaults; set real values anywhere else):

- `UPLOAD_DIR` — where staged guest uploads live (`./uploads` locally, `/data/uploads` in the dev compose stack, backed by the `uploads` named volume). Uploads are never served by the web container; moderators stream them through `GET /api/v1/moderation/submissions/{id}/uploads/{upload_id}`.
- `AUTH_SECRET` — signs fastapi-users reset/verify tokens.
- `COOKIE_SECURE` — `false` by default so the session cookie works over local http; set `true` behind https.
- `RATE_LIMIT_SALT` — salts the client-net and login-attempt hash keys so IPs/emails are never stored raw.

Create a moderator account (invite-only; there is no self-registration):

```sh
cd services/backend && uv run python scripts/create_moderator.py <email>
# prints a generated password; pass --password to set one explicitly
```

Known stubs and caveats:

- Rate limiting is `InMemoryRateLimiter` — per-process, not shared across workers. A Redis backend is the planned upgrade and slots in through the `RateLimiter` seam (`app.security.get_rate_limiter`) without touching call sites.
- Access tokens are created with `lifetime_seconds=None` — sessions live until logout deletes the row; there is no expiry sweep.
- Outbox `dispatch_pending` (`app.services.outbox`) ships with a `LoggingPublisher` stub that only logs; a real broker publisher arrives with the Celery screening plan.
- The uploads sweeper must cascade deletion off the submission row: purging a submission deletes its upload files under `UPLOAD_DIR` together with their `upload` rows.

## Tests

```sh
cd services/backend && uv run pytest        # backend unit/API tests (SQLite)
pnpm --filter @jejakpeluang/web test        # web component tests
pnpm --filter @jejakpeluang/web lint        # eslint
pnpm --filter @jejakpeluang/web build       # production build
pnpm --filter @jejakpeluang/e2e exec playwright install chromium   # one-time
pnpm --filter @jejakpeluang/e2e test:e2e    # needs the compose stack up
```
