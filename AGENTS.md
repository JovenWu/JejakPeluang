# Agent notes

## Toolchain on this host

Node is not installed on the host; run all JS tooling in `node:24-alpine` as uid 1000
(so files stay owned by `ubuntu`) with the repo mounted at `/w`:

```sh
J="docker run --rm --user 1000:1000 -e HOME=/tmp -e COREPACK_HOME=/tmp/corepack -v $PWD:/w"
$J --network host -e CI=true -w /w node:24-alpine corepack pnpm@10.33.0 install --store-dir /w/.pnpm-store
$J -w /w/apps/web node:24-alpine node_modules/.bin/tsc --noEmit
$J -w /w/apps/web node:24-alpine node_modules/.bin/eslint .
$J -e TZ=UTC -w /w/apps/web node:24-alpine node_modules/.bin/vitest run
$J -w /w/apps/web node:24-alpine node_modules/.bin/next build
# dev server against the running compose API (port 3000 is the compose web container)
$J --network host -e API_INTERNAL_ORIGIN=http://127.0.0.1:8000 -w /w/apps/web node:24-alpine \
  node_modules/.bin/next dev -p 3001 -H 127.0.0.1
```

`infra/.env` has no `NODE_IMAGE`; pass it inline when building the web image:
`NODE_IMAGE=node:24-alpine@sha256:<digest> docker compose --env-file infra/.env -f infra/compose.dev.yml build web`

## Web UI conventions (`apps/web`)

- Bahasa Indonesia copy. AI output is evidence, never a verdict: no "aman"/"penipuan"/"safe"/"scam"
  wording in any AI-derived label (enforced by `src/lib/screening.test.ts`).
- Trust marks: `components/stamp.tsx` — solid = moderator verified, filled = issuer confirmed
  privately, dashed = AI-checked only. Use it instead of ad-hoc badges.
- Receipt tokens never go in query strings: `sessionStorage` or the `#token=` fragment only.
- Status polling backs off (`POLL_DELAYS` in `submission-view.tsx`) to stay under the 30/hour limit.
- Dates: deadlines are date-only and must be computed in `Asia/Jakarta` (`lib/format.ts`).
- Backend `/users/me` returns 500 for emails on reserved TLDs (e.g. `.local`); use real-looking
  domains for test moderator accounts.

## Renderer (JavaScript pages)

- `renderer` compose service = `app/renderer.py` + `app/services/render.py`; worker reaches it via
  `RENDERER_URL=http://renderer:9000`. Every browser request goes through `fetch()`; never give the
  browser direct network access or put it on the default network.
- Rebuild after touching fetch/render code: `docker compose ... up -d --build renderer worker`
  (export `NODE_IMAGE` first; see above).
- Judged/production web server: container `jp-web`, `next start` bound to the Tailscale IP
  `100.125.32.82:3001`. After frontend changes: `next build` (see above) then `docker restart jp-web`.
