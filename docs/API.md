# Turium HTTP API

Base URL in development: `http://localhost:8000`. The web client talks to `/api/*`, which the
Vite dev server proxies to the backend (stripping the `/api` prefix). All bodies are JSON;
all timestamps are ISO 8601 UTC.

## Conventions

- **Error envelope**: every non-2xx response has this shape:

  ```json
  { "error": { "code": "FETCH_FAILED", "message": "human readable", "details": { } } }
  ```

- **Request ID**: every response carries `X-Request-ID`. Send your own to trace a call
  end-to-end through the JSON logs.

- **Status codes**

  | Code | Meaning |
  |------|---------|
  | `VALIDATION_ERROR` | 422: schema/limits violated (including no usable content) |
  | `NOT_FOUND` | 404: item or route does not exist |
  | `DUPLICATE_ITEM` | 409: identical content already saved (`details.item_id`) |
  | `INVALID_URL` | 400: not a valid http/https URL |
  | `BLOCKED_URL` | 400: resolves to a private/loopback/reserved address |
  | `UNSUPPORTED_CONTENT_TYPE` | 415: page is not text/html or text/plain |
  | `CONTENT_TOO_LARGE` | 413: page exceeds `FETCH_MAX_BYTES` |
  | `FETCH_FAILED` | 502: upstream fetch failed (timeout, DNS, non-2xx) |
  | `UPSTREAM_AI_ERROR` | 502: embedding/chat provider call failed |
  | `INTERNAL_ERROR` | 500: unexpected server error (check logs via `X-Request-ID`) |

## GET /health

Liveness plus the active AI mode and corpus size.

```bash
curl http://localhost:8000/health
```

```json
{ "status": "ok", "provider": "offline", "chat_model": "offline-extractive",
  "embedding_model": "offline-hashing-512", "items": 2, "chunks": 7 }
```

With `OPENAI_API_KEY` set, `provider` becomes `openai` and the model fields report the
configured OpenAI models.

## POST /ingest

Save a note or a URL. Returns 201 with the created item and how many chunks were indexed.

### Note

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"type":"note","content":"Postgres uses MVCC for concurrency control.","title":"DB notes"}'
```

### URL

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"type":"url","url":"https://en.wikipedia.org/wiki/Retrieval-augmented_generation"}'
```

Fields:

| Field | Type | Notes |
|-------|------|-------|
| `type` | `"note"` \| `"url"` | required, discriminator |
| `content` | string | notes only, 1–100,000 chars |
| `url` | string | URL only, ≤ 2048 chars, http/https |
| `title` | string \| null | optional, ≤ 200 chars; for URLs defaults to the page `<title>` |

Response (201):

```json
{ "item": { "id": "3f2c…", "type": "url", "title": "Retrieval-augmented generation",
            "source": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
            "created_at": "2026-09-10T14:22:31+00:00", "char_count": 8123, "chunk_count": 9 },
  "chunks_created": 9 }
```

Errors: 422 (bad payload, empty content), 409 (duplicate), 400/413/415/502 for URL issues.

> **Google Docs / Sheets / Slides:** the `/edit` links are JavaScript apps: a plain fetch only
> sees a browser-support shell. Turium detects them and fetches the export endpoint instead
> (`text/plain` for Docs/Slides, `text/csv` for Sheets), keeping the original link as `source`.
> The document must be shared as "Anyone with the link", otherwise ingest fails with a clear 502
> message instead of indexing an empty shell.

## GET /items

Newest first. Pagination: `limit` 1–100 (default 50), `offset` ≥ 0.

```bash
curl "http://localhost:8000/items?limit=20&offset=0"
```

```json
{ "items": [ { "id": "3f2c…", "type": "note", "title": "DB notes", "source": null,
               "created_at": "2026-09-10T14:20:02+00:00", "char_count": 412, "chunk_count": 1 } ],
  "total": 12, "limit": 20, "offset": 0 }
```

## GET /items/{id}

Item metadata plus every stored chunk with character offsets, useful for inspecting what the
chunker produced.

```bash
curl http://localhost:8000/items/3f2c…
```

```json
{ "item": { "id": "3f2c…", "type": "note", "title": "DB notes", "source": null,
            "created_at": "2026-09-10T14:20:02+00:00", "char_count": 412, "chunk_count": 1 },
  "chunks": [ { "id": "9a01…", "chunk_index": 0, "content": "Postgres uses MVCC…",
                "char_start": 0, "char_end": 412, "embedding_model": "offline-hashing-512" } ] }
```

Errors: 404.

## DELETE /items/{id}

Deletes the item and its chunks (cascade). Returns 204 with no body.

```bash
curl -X DELETE http://localhost:8000/items/3f2c… -i
```

Errors: 404.

## POST /query

Ask a question over everything saved. Retrieves the top-k chunks by cosine similarity, then
answers with a grounded prompt. Citations are 1-based and match bracketed markers in the answer.

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What did I save about Postgres concurrency?","top_k":5}'
```

Fields: `question` 1–1000 chars (trimmed), `top_k` 1–20 (default `DEFAULT_TOP_K`, 5).

```json
{ "answer": "You saved that Postgres uses MVCC for concurrency control [1].",
  "citations": [
    { "index": 1, "item_id": "3f2c…", "chunk_id": "9a01…", "title": "DB notes",
      "source": null, "type": "note", "snippet": "Postgres uses MVCC…", "score": 0.82 }
  ],
  "provider": "offline", "model": "offline-extractive", "retrieved": 1,
  "latency_ms": 14, "warnings": [] }
```

Notes:

- The `answer` field is **markdown**: the web client renders lists, bold, headings and code.
  Provider-specific citation glyphs (e.g. `【1†L1-L4】`) are normalized to `[k]` server-side.
- With an **empty knowledge base** the response is 200 with a canned
  `"You haven't saved anything yet. Add a note or URL first."` and no citations. No LLM call.
- With **no relevant retrieval** the answer says so instead of guessing.
- `warnings` reports skipped chunks when they were embedded with a different model/dimension
  (e.g. you ingested offline, then enabled OpenAI). Re-ingest after switching providers.

Errors: 422 (empty/oversized question, `top_k` out of range), 502 (provider failure).
