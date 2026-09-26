# JejakPeluang

National catalogue of verified scholarships, internships, and competitions for Indonesian students. Every entry is reviewed by a human moderator and linked to its original source.

Public catalogue + controlled intake — Next.js Bahasa Indonesia UI (`apps/web`), FastAPI + PostgreSQL backend (`services/backend`), shared OpenAPI types (`packages/contracts`), and a Playwright end-to-end flow (`tests/e2e`). Guest submissions and uploads feed an invite-only moderator queue. An asynchronous screening pipeline (Tavily discovery -> SSRF-hardened fetch -> OpenRouter extraction/comparison -> TypeSafe Jev typed judgments) prepares structured evidence for moderators — it never publishes anything and never emits scam/safe verdicts; only a moderator's approval creates a listing.

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

## Screening pipeline (backend)

Each accepted submission gets a `screening_runs` row plus a `job_outbox`
entry in the same transaction. The `worker` service (Redis `BLPOP` fast path
+ periodic DB sweep, so a lost message or crashed worker never strands a
submission) executes `run_screening` idempotently by run id:

1. **Gather** — extract text from uploaded PDFs (`pypdf`) and/or the
   submitted URL through the SSRF-hardened fetcher.
2. **Extract** — OpenRouter (`response_format` JSON schema, `temperature 0`)
   pulls title/issuer/deadline/category/region/eligibility/fees/
   requested_data from the submitted text.
3. **Discover** — Tavily finds candidate public sources with a minimized
   title+issuer query (verified issuer domains are searched first). Search
   snippets are leads, never evidence.
4. **Fetch evidence** — `app/services/fetch.py` resolves every hop itself,
   requires all candidate IPs to be public, pins the connection to the
   validated IP (Host header + SNI preserved), follows redirects only after
   re-validating each destination, and caps response size/redirects/timeouts.
5. **Compare** — OpenRouter emits per-field `supported/conflicting/
   not_found/unreadable` verdicts with short verbatim quotes.
6. **Judge** — TypeSafe Jev answers typed questions per fetched page
   (`official_announcement` noul, `doc_kind` choice, `source_authority`
   score, `deadline_corroborated` noul), each with probabilities/confidence.
   `ai_source_match` on the published listing is true only when at least one
   fetched page was judged an official issuer listing with no conflicting
   field verdicts.

Runs always terminate in a moderator-visible outcome: `complete`,
`provider_unavailable`, `manual_review_required` (malformed model output),
`no_public_source`, or `no_content`. Provider calls retry transient failures
(timeouts, connection errors, 429, 5xx) with capped exponential backoff +
jitter and honour `Retry-After` up to 30 s — a longer delay becomes
`provider_unavailable` instead of wedging the worker past the run deadline;
exhausted retries degrade the outcome rather than failing intake. Workers bound each run to 3 attempts; a hard failure or
stale run lands in `failed` for the moderator to see.

The `sweeper` service runs `scripts/sweep_retention.py` hourly: deletes
expired uploads from disk + rows, purges `submission_text`/`evidence[].text`
and contact emails once `purge_after` passes, closes stale queued/processing
submissions after `STALE_HOURS` (72) and any still-open submission once its
30-day window ends, removes expired access-token rows, and clears orphaned
staging files after `STAGING_MAX_AGE_HOURS` (24). Any terminal moderator
decision — approve, reject, or expire — shortens submission retention to
7 days from the decision.

Provider + runtime variables (also see `infra/.env.example`):

- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `openai/gpt-6-luna`),
  `OPENROUTER_BASE_URL`
- `TYPESAFE_API_KEY`, `TYPESAFE_MODEL` (default `jev-latest`)
- `TAVILY_API_KEY`, `TAVILY_BASE_URL`
- `REDIS_URL` — enables the Redis outbox broker + shared rate limiter.
  `JOB_BROKER=redis` requires it. Without Redis the worker polls the DB:
  fresh queued runs wait up to `SWEEP_INTERVAL_SECONDS` (30 s) before
  dispatch — fine for dev, set Redis for prompt processing.
- `RATE_LIMITER=redis` — shared fixed-window limiter (INCR+EXPIRE);
  default `memory` is per-process. The Redis limiter fails open with a
  warning if the backend is unreachable.
- `TRUSTED_PROXY_CIDRS` — comma-separated CIDRs of trusted reverse proxies
  (e.g. `172.18.0.0/16` for the Traefik network). Only requests whose socket
  peer is inside these ranges may set `X-Forwarded-For`-derived client
  identity for rate limiting; without it every proxied guest shares one
  bucket. Leave empty when clients connect directly.
- `ACCESS_TOKEN_TTL_SECONDS` — moderator session TTL, default 28800 (8 h);
  expired token rows are removed by the retention sweep.
- `APP_ENV=production` — startup fails unless `AUTH_SECRET`/`RATE_LIMIT_SALT`
  are non-default, `COOKIE_SECURE=true`, and `JOB_BROKER=redis` has
  `REDIS_URL`.

Set provider keys via `infra/.env` (gitignored) — they are interpolated into
the api/worker/sweeper containers only.

## Known caveats

- Uploads are sniffed by content (magic bytes + pypdf parse); an AV scanner
  seam exists via `FileScanner` (`app.services.submissions.get_scanner`) —
  drop in a ClamAV adapter behind the same protocol for production.
- Request body size is enforced per-upload (10 MB per file, 20 MB total,
  3 files); the front proxy should also cap total request size (e.g. Traefik
  `buffering.maxRequestBodyBytes` or nginx `client_max_body_size 32m`).
- The worker runs screening sequentially per process; scale by adding
  worker replicas — concurrent processing of the same run is prevented by an
  atomic state-claim UPDATE, and runs are idempotent by run id.
  Single-replica is the default.

## Tests

```sh
cd services/backend && uv run pytest        # backend unit/API tests (SQLite)
# live provider checks (costs small credits; keys sourced from infra/.env):
JP_LIVE_TESTS=1 uv run pytest -m live -q
# full-stack smoke test (compose stack up + migrated):
docker compose --env-file infra/.env -f infra/compose.dev.yml exec -T api \
    uv run --no-sync python scripts/e2e_check.py
pnpm --filter @jejakpeluang/web test        # web component tests
pnpm --filter @jejakpeluang/web lint        # eslint
pnpm --filter @jejakpeluang/web build       # production build
pnpm --filter @jejakpeluang/e2e exec playwright install chromium   # one-time
pnpm --filter @jejakpeluang/e2e test:e2e    # needs the compose stack up
```
