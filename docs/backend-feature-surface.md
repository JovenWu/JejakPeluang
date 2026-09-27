# JejakPeluang — Backend Feature Surface (for UI/UX design)

This document describes **everything the backend can do** — actors, journeys,
endpoints, payloads, states, and constraints. Design the interface from
scratch against this; nothing here prescribes or assumes any existing UI.

## Product in one paragraph

An instant **AI fact-check** for Indonesian opportunity posts, plus a
national catalogue of **verified** scholarships, internships, and
competitions. A guest drops a link or uploads a poster; within seconds the
AI returns what it found: extracted details (deadline, fees, requested
documents), whether an official issuer page exists, and which fields match
it. That instant result is the product's core value. Two public surfaces
exist: an **incoming feed** of AI-checked submissions awaiting review
(`verification: 'ai_checked'`) and the **catalogue** of
moderator-approved listings (`verification: 'moderator_verified'`).
**A human always makes the publish decision** — the AI never publishes and
never emits scam/safe verdicts; it reports facts and source matches.
Primary audience language is **Bahasa Indonesia**.

## Actors

| Actor | Identity | What they do |
|---|---|---|
| Guest | Anonymous; identified only by a one-time **receipt token** | Submit an opportunity, **see its AI check result immediately**, track status, browse catalogue + incoming feed, file reports |
| Moderator | Cookie-session account (`role=moderator`), invite-only — no self-registration | Review queue, inspect AI evidence, approve/reject/expire submissions |
| System | Screening worker + retention sweeper | Extract/discover/compare/judge automatically after intake |

## Core journeys the UI must support

### 1. Guest submission

`POST /api/v1/submissions` — `multipart/form-data`, returns `202`.

| Field | Rules |
|---|---|
| `url` | optional; `http`/`https` only, ≤2048 chars. Required *or* ≥1 file |
| `context` | optional free text, ≤4096 chars |
| `contact_email` | optional, valid email |
| `files` | 0–3 files; PDF/PNG/JPG sniffed by content (magic bytes, not extension); ≤10 MB each, ≤20 MB total |

Response — **the receipt token is shown exactly once**; the backend stores
only its hash and cannot recover it:

```json
{ "ref": "JP-DHD1X8GR", "receipt_token": "5vRHgG...", "status": "queued",
  "status_url": "/api/v1/submissions/JP-DHD1X8GR" }
```

Errors: `422` with `detail` explaining the rejection (bad URL, oversized
context, no url+files, bad file type/size); `429` when over rate limit
(10 submissions/hour).

**UX consequence:** the receipt screen must make the token prominent and
copyable/downloadable — without it the guest can never check status again.

### 2. Guest status check

`GET /api/v1/submissions/{ref}` — requires header `X-Receipt-Token`.
Returns `401` without/with a wrong token, `404` for unknown ref,
`429` over 30/hour.

```json
{ "ref": "JP-DHD1X8GR", "state": "review_pending",
  "status_label": "Menunggu peninjauan moderator",
  "created_at": "2026-09-26T19:00:00Z",
  "decision": null, "needs_more_evidence": false,
  "screening": {
    "state": "complete", "outcome": "complete",
    "extracted": { "title": "Beasiswa Unggulan",
        "issuer": "Kemendikbudristek", "deadline": "2026-11-30",
        "category": "scholarship", "fees": "gratis",
        "requested_data": ["CV"] },
    "field_verdicts": { "deadline": { "verdict": "supported",
        "quote": "s.d. 30 November 2026" }, "issuer": { "verdict": "…" } },
    "sources": [{ "url": "https://beasiswaunggulan.kemdikbud.go.id",
        "status": 200, "official": true }],
    "ai_source_match": true,
    "errors": [{ "stage": "discovery", "kind": "unavailable" }],
    "finished_at": "2026-09-26T19:00:42Z" } }
```

`state` lifecycle: `received` → `queued` → `processing` → `review_pending`
→ terminal: `published` | `rejected` | `expired` | `closed_unreviewed`.
`status_label` is pre-translated Indonesian — use it or map `state`
yourself. `needs_more_evidence: true` means a moderator asked for more info
(submission stays `review_pending`); the API exposes no resubmit channel —
decide how a guest should act on that (e.g., fresh submission).

**`screening` is the instant AI result** — the product's core payoff:

- `screening.state` mirrors the run: `queued` → `processing` → `complete` |
  `failed`. Poll until `complete`/`failed` (seconds-to-a-minute).
- `extracted` — structured fields the AI read from the guest's own post
  (deadline, **fees**, **requested_data** — the scam signals users check
  for). `null` until extracted.
- `field_verdicts` — per-field comparison vs fetched sources:
  `supported` | `conflicting` | `not_found` | `unreadable`, with verbatim
  `quote`. Ideal for a field-by-field compare table.
- `sources` — fetched candidate pages: `status` + `official` (Jev judged
  it the issuer's official listing). `official: null` = unjudged.
- `ai_source_match` — `true` when ≥1 fetched page was judged official with
  no field conflicts; `false`/`null` otherwise.
- `outcome` — `complete` | `provider_unavailable` | `manual_review_required`
  | `no_public_source` | `no_content`. Non-`complete` outcomes are honest
  degradations — explain, don't hide.
- `errors` — `stage` + `kind` only (provider internals withheld).

The projection is **deliberately sanitized**: no `submission_text`, no
evidence body text, no contact email, no context echo, no provider/model
internals — only the guest's own extracted facts and public web facts.
**Never render it as a verdict** — the AI found facts and sources; it does
not say "safe" or "scam".

### 3. Incoming feed — AI-checked, awaiting verification (public)

`GET /api/v1/opportunities/incoming` — anonymous. The live feed of
submissions that finished AI screening and await moderator review.
`limit` (1–50, default 20), `offset`; newest first.

```json
{ "items": [{ "ref": "JP-DHD1X8GR", "created_at": "…",
    "verification": "ai_checked",
    "submitted_url": "https://contoh.id/pengumuman",
    "screening": { "…same projection as the guest status object…" } }],
  "total": 7 }
```

`GET /api/v1/opportunities/incoming/{ref}` — same item shape for a detail
view. `404` for unknown refs **and** for submissions that already left the
queue (approved/rejected/expired) — the item graduates out of the feed.

Design cautions — these are **unvetted submissions**:

- `verification: 'ai_checked'` is the badge value; pair it with copy like
  *"Dicek AI — belum diverifikasi moderator"* so users never mistake it
  for endorsement. When a moderator approves, the same content reappears
  in the catalogue as `verification: 'moderator_verified'`.
- `extracted` fields come from the submission itself — a scam post yields
  scam-flavored fields (fees, KTP requests). That's the honest check
  result; show it as evidence, not as a warning banner authored by the
  app.
- `screening.outcome` may be `no_public_source`/`provider_unavailable`/
  `no_content` — cards need graceful "check inconclusive" states.
- Feed rows expose no guest PII, uploads, or context — only the submitted
  URL plus the sanitized screening projection.

### 4. Public catalogue

`GET /api/v1/opportunities` — anonymous. Query params:
`category` (`scholarship` | `internship` | `competition`), `q`
(title substring search), `limit` (1–50, default 20), `offset`.

```json
{ "items": [{ "slug": "beasiswa-unggulan-…", "title": "…",
    "category": "scholarship", "issuer_name": "Kemendikbudristek",
    "deadline": "2026-11-30", "checked_at": "…", "verified_at": "…",
    "trust_basis": "public_source", "verification": "moderator_verified",
    "status": "published", "source_url": "https://…",
    "ai_source_match": true }],
  "total": 42 }
```

`GET /api/v1/opportunities/{slug}` — adds `description`, `eligibility`,
`region`. Detail also serves `expired`/`needs_review` rows (list shows only
`published`) — so deep links must render a non-published state gracefully.

Field semantics that matter for design:

- `verification` — always `'moderator_verified'` on catalogue items (a
  human approved each one). The paired value `'ai_checked'` appears only on
  the incoming feed — one badge component can render both tiers.
- `source_url` — the verified public source; **`null` for
  `trust_basis='issuer_confirmed_private'`** listings (moderator attested
  the issuer privately; nothing public to link). Handle "no link" listings.
- `ai_source_match` — `true` when the AI found a fetched page it judges an
  official issuer listing with no field conflicts; `false` when evidence
  existed but none qualified; `null` when unscreened. **Advisory signal
  only** — not a guarantee; treat as a light badge, not a certification.
- `deadline` may be `null`; sorting puts null-deadline items last.
- `checked_at`/`verified_at` = "last verified" timestamps — candidate
  trust-display material.

### 5. Community report (public)

`POST /api/v1/opportunities/{slug}/reports` — anonymous, `201`, JSON body:

```json
{ "category": "scam_suspect|deadline_wrong|link_broken|info_incorrect|other",
  "description": "optional, ≤2000 chars" }
```

Rate limit 20/hour. Reports are **advisory only** — they never change the
listing's status or visibility; they surface a badge on the moderator's
queue row. No feedback loop to the reporter exists.

### 6. Moderator auth

- `POST /api/v1/auth/login` — `application/x-www-form-urlencoded`
  `username` + `password` (OAuth2 form). `204` + `Set-Cookie: jp_auth`
  (HttpOnly, SameSite=Lax, 8 h TTL). `400` bad credentials, `429` after
  5 attempts/minute.
- `POST /api/v1/auth/logout` — `204`.
- `GET /api/v1/users/me` — current user (has `role`).
- **CSRF:** any unsafe request carrying the cookie must send `Origin` or
  `Referer` matching the host — same-origin SPA is naturally fine.
- No self-registration, no password reset UI flow — accounts are created
  server-side by an operator.

### 7. Moderation queue

`GET /api/v1/moderation/submissions?state=&limit=&offset=` — auth required
(`401`/`403` otherwise). Oldest first.

```json
{ "items": [{ "id": "…", "ref": "JP-…", "state": "review_pending",
    "created_at": "…", "submitted_url_host": "kemdikbud.go.id",
    "uploads_count": 2, "has_contact_email": true,
    "open_reports_count": 3 }], "total": 17 }
```

`state` filter is free-form over the lifecycle states above; `review_pending`
is the actionable queue.

### 8. Submission detail (the evidence page)

`GET /api/v1/moderation/submissions/{id}` — everything a moderator needs:

```json
{ "id": "…", "ref": "JP-…", "state": "review_pending",
  "submitted_url": "https://…", "context": "guest's free text",
  "contact_email": "guest@…", "client_net_hash": "…(opaque)",
  "purge_after": "…", "created_at": "…", "updated_at": "…",
  "uploads": [{ "id": "…", "storage_key": "…", "detected_mime":
      "application/pdf", "size_bytes": 1024, "page_count": 2 }],
  "screening_run": { "id": "…", "state": "complete",
      "provider_version": "openrouter+tavily+typesafe-jev",
      "model_version": "openai/gpt-6-luna+jev-1.13.0",
      "schema_version": "…", "result_json": {…see below…},
      "error": null, "finished_at": "…", "created_at": "…" },
  "decisions": [{ "id": "…", "status": "approved", "reason": "…",
      "actor_id": "…", "decided_at": "…" }],
  "linked_opportunity_slug": "…|null",
  "reports": [{ "id": "…", "category": "scam_suspect",
      "description": "…", "status": "open", "created_at": "…" }] }
```

Uploads stream through
`GET /api/v1/moderation/submissions/{id}/uploads/{upload_id}` — render
PDFs/images inline if desired.

#### `result_json` — the AI evidence payload

```json
{ "schema_version": "…", "outcome": "complete",
  "submission_text": "extracted text (purged after retention)",
  "extraction": { "title": "…", "issuer": "…", "deadline": "2026-11-30",
      "category": "scholarship", "region": "…", "eligibility": "…",
      "fees": "gratis|Rp150.000|…", "requested_data": ["CV","KTP"],
      "source_hint": "…" },
  "discovery": { "status": "searched|skipped", "query": "title issuer",
      "results": [{ "url": "…", "title": "…", "score": 0.9 }] },
  "evidence": [{ "url": "…", "final_url": "…", "status": 200,
      "content_type": "text/html", "fetched_at": "…",
      "text": "fetched page text (purged after retention)" }],
  "comparison": { "field_verdicts": { "title": {"verdict":"supported",
        "quote":"verbatim excerpt"}, "issuer": {…}, "deadline": {…},
        "category": {…}, "region": {…}, "eligibility": {…} },
      "notes": "neutral two-sentence note|null" },
  "judgments": [{ "url": "…", "answers": {
      "official_announcement": {"type":"noul","noul":0.98},
      "doc_kind": {"type":"choice","choice":"official_listing",
          "probabilities":{…},"confidence":0.97},
      "source_authority": {"type":"score","score":0.9},
      "deadline_corroborated": {"type":"noul","noul":0.95} } }],
  "ai_source_match": true,
  "errors": [{ "stage": "fetch|extract|discover|compare|judge",
      "kind": "…", "detail": "…" }] }
```

- `outcome`: `complete` | `provider_unavailable` | `manual_review_required`
  | `no_public_source` | `no_content`. Non-`complete` outcomes are honest
  degradations, not failures — the UI should explain them, not hide them.
- `verdict` values: `supported` | `conflicting` | `not_found` |
  `unreadable`, each with a verbatim `quote` — designed for a
  field-by-field compare table.
- `noul` = probability the answer is "true" (0–1). `doc_kind` choices:
  `official_listing` | `aggregator` | `unrelated`.
- `evidence[].text` and `submission_text` disappear after retention purge —
  render "purged" states (`text_purged: true`).
- `screening_run.state`: `queued` | `processing` | `complete` | `failed`
  (with `error`). A `failed`/absent run still allows a decision — the AI is
  advisory.

### 9. Moderator decision

`POST /api/v1/moderation/submissions/{id}/decision`:

```json
{ "decision": "approved|needs_more_evidence|rejected|expire",
  "reason": "optional ≤2000",
  "fields": {                      // required iff decision == 'approved'
    "title": "≤240", "category": "scholarship|internship|competition",
    "description": "required", "eligibility": "required",
    "region": "opt ≤160", "deadline": "YYYY-MM-DD opt",
    "slug": "opt, lowercase-hyphen or auto-derived from title",
    "issuer_name": "opt; REQUIRED when trust_basis is private",
    "trust_basis": "public_source|issuer_confirmed_private" } }
```

Response: `{ id, status, submission_id, submission_state,
opportunity_slug }` — `opportunity_slug` is set only on approval.

- `public_source` approval requires the submission to have a
  `submitted_url` (it becomes the listing's `source_url`); otherwise `422`.
- `issuer_confirmed_private` = moderator attests issuer identity privately —
  publishes with **no public source URL**.
- `409` on double-approve or slug conflict; `409` on deciding an already
  terminal submission. Approval prefills nothing — but `extraction` fields
  are designed to populate the form.

## Constraints that shape the UX

- **Human gate governs the catalogue.** No state lets AI publish a listing;
  treat AI output as evidence cards, never verdicts. Do not display
  `ai_source_match` or Jev answers as "safe/scam" language.
- **The incoming feed is unvetted by design.** `ai_checked` items are raw
  submissions that finished screening — anyone can get content in via a
  rate-limited form. The badge/copy must always convey "AI-checked, pending
  human review", never imply endorsement.
- **Instant result, asynchronous compute.** Screening takes
  seconds-to-a-minute after submission; the status page should poll
  `screening.state` until `complete`/`failed`, then render the projection.
- **Privacy clock.** Guest PII, uploads, and extracted text delete 30 days
  after intake, or **7 days after any terminal decision**. Status checks
  and moderator views degrade gracefully (`contact_email: null`,
  `text_purged`); screening projections survive in sanitized form.
- **Rate limits** guests will hit: 10 submits/hr, 30 status polls/hr,
  20 reports/hr — surface `429` with retry-later copy.
- **Receipts are bearer secrets.** `X-Receipt-Token` is the only guest
  credential; lost token = lost submission access. Refs alone are
  enumerable-safe but useless without the token.
- **Reports can't be resolved via API** (no triage endpoint) — they're a
  signal counter on the queue and a list on the detail page only.
- **No notifications** — no email/SMS/webhook to guests exists; the status
  page is the only feedback channel.
- **Two trust tiers everywhere.** `verification: 'ai_checked'` =
  screened submission awaiting review; `'moderator_verified'` = human-
  approved catalogue listing. `verified_at` is when a moderator approved
  it; `trust_basis` distinguishes public-source vs privately-confirmed
  listings.

## Language & content notes

- Catalogue content is Indonesian-first; backend status labels already ship
  in Bahasa Indonesia (`Diterima`, `Dalam antrean`, `Sedang diproses`,
  `Menunggu peninjauan moderator`, `Dipublikasikan`, `Ditutup tanpa
  peninjauan`, `Ditutup`).
- Submission content is mixed Indonesian/English (posters, chat forwards,
  PDFs) — extraction handles both.
