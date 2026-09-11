# Turium: Design Notes & Tradeoffs

This document is the reasoning behind the implementation. The frozen build contract lives in
[`SPEC.md`](./SPEC.md); the HTTP surface is documented in [`API.md`](./API.md).

## 1. System overview

```
                 ┌─────────────────────────── FastAPI (sync, threadpool) ───────────────────────────┐
                 │                                                                                  │
 React (Vite)    │  POST /ingest ──► fetcher (httpx+bs4, SSRF guard) ──► chunker ──► embedding provider│
 /api/* proxy ───┼──► try/except: notes skip the fetch step                                             │
                 │                                              │                                        │
                 │                                              ▼                                        │
                 │                           SQLite: items + chunks(embedding BLOB, float32, L2-normalized)│
                 │                                              │                                        │
                 │  POST /query ──► embed question ──► cosine top-k (numpy) ──► chat provider ──► answer   │
                 │                                              + citation metadata + latency/warnings    │
                 └──────────────────────────────────────────────────────────────────────────────────────┘
```

Two request flows:

- **Ingest**: validate payload → (URL only) fetch + extract text → normalize → chunk →
  embed chunks in one provider call → insert item + chunks in one SQLite transaction.
- **Query**: validate → embed question → cosine top-k against stored chunk vectors →
  build numbered citation context → ask the chat provider with a grounded prompt → return
  answer + citations + metadata.

Everything is designed to run with **zero external services** (offline provider) and to
upgrade to OpenAI by setting one env var. The provider interface is the seam.

## 2. Chunking strategy, and why

**Chosen: character-based, structure-aware packing. Max 1000 chars, 150-char overlap,
50-char minimum merge.**

Algorithm (deterministic): normalize whitespace → split on blank lines into paragraphs →
greedily pack paragraphs up to the limit → for oversized paragraphs, pack sentences →
for oversized sentences, split at word boundaries → prepend a word-boundary-trimmed overlap
tail to each new chunk → merge a tiny trailing chunk into the previous one.

The implementation works on **character spans** of the normalized text, so every chunk is
exactly `normalized[char_start:char_end]`: offsets are exact, chunk text is never mutated, and
overlap is clipped to the remaining size budget instead of overflowing (a naive prepend can
silently drop the tail of a chunk, a data-loss bug this design rules out). Tests assert
verbatim content, full coverage of non-whitespace input, and the size cap.

Rationale:

- **Paragraph/sentence boundaries beat fixed windows.** Notes and articles are organized in
  semantic units; splitting mid-sentence degrades both the embedding and the answer quality.
  Fixed-width windows are simplest but produce noisy chunks at boundaries.
- **~1000 chars (~250 English tokens) is a deliberate retrieval/generation balance.** Small
  chunks give precise retrieval but lose context and multiply vector count; large chunks give
  context but blur what the vector represents. 1000/150 keeps each chunk focused while the
  overlap preserves context that straddles a boundary.
- **Characters, not tokens.** A tokenizer dependency (tiktoken) buys accuracy we don't need at
  this scale, at the cost of a heavier, model-coupled ingest path. Chars are language-agnostic,
  deterministic, and (critically) cheap to unit test. Model context windows are large enough
  that a ±25% token estimate error is irrelevant here.
- **No semantic/recursive-LLM chunking.** Better in theory, but it costs an LLM pass per item,
  makes ingest non-deterministic and untestable offline, and is overkill for short notes.
  Documented as a production upgrade path.

Tradeoffs accepted: code blocks and tables can be split awkwardly (word-boundary split is the
fallback); overlap duplication slightly inflates storage and can produce duplicate top-k hits
(mitigation: dedupe by chunk id at retrieval, which is inherent).

## 3. Embeddings: provider abstraction with an offline fallback

The assignment wants OpenAI *or equivalent*. Since a reviewer may not have a key, the app ships:

- `AI_PROVIDER=openai`: `text-embedding-3-small` (1536-d) + `gpt-4o-mini` chat, grounded
  prompt with bracketed citations and an explicit "not in your saved content" instruction.
  Models sometimes emit provider-specific citation glyphs (`【1†L1-L4】`); these are normalized
  to `[k]` at the provider boundary, and the web client renders answers as markdown.
- `AI_PROVIDER=offline`: deterministic fallback so the full pipeline runs without any key:
  - Embeddings: the **hashing trick** with sparse signed indexing: tokenize, hash each token
    with `blake2b`, map it to one dimension (`hash % dim`) with a stable sign bit, weight by
    `1 + ln(tf)`, L2-normalize. Sparse indexing matters: disjoint vocabularies get a cosine of
    exactly 0 (dense random projections would give every pair a small accidental similarity).
    This is *lexical* similarity, not semantic. Be honest about it: it exists for demo-ability
    and deterministic tests, and the UI labels it.
  - Chat: extractive answering: score source sentences against the question with the same
    embedding, return the best few with `[k]` markers. No hallucination by construction.
- `AI_PROVIDER=auto` (default): picks OpenAI when `OPENAI_API_KEY` is set, otherwise offline,
  and logs the choice at startup. `/health` reports the active mode so the UI can badge it.

The OpenAI provider is a standard OpenAI-compatible client (`OPENAI_BASE_URL` override), so
gateways like OpenRouter work without code changes. This build was verified end-to-end against
OpenRouter with `openai/text-embedding-3-small` for embeddings and
`nvidia/nemotron-3-super-120b-a12b:free` for answers, a free model that follows the grounded
prompt, cites `[k]` correctly, and refuses cleanly when the answer is not in context.

Why not a local transformer (sentence-transformers/ONNX)? It would give real semantic quality
offline, but adds ~100 MB model downloads and heavy dependencies to a 6–12 hour assignment.
The abstraction makes it a drop-in provider later.

**Provider switching caveat (handled):** vectors from different models are not comparable.
Every chunk row stores `embedding_model`, `embedding_provider`, and `embedding_dim`; retrieval
filters to the current dimension and returns a warning when mismatched chunks were skipped.
Re-embedding after a provider switch is documented as a production job (out of scope here).

## 4. Vector store: SQLite + in-process numpy cosine

**Chosen: embeddings stored as float32 BLOBs in the same SQLite database as the content,
brute-force cosine similarity computed in-process with numpy.**

Rationale:

- Single user, single process, small corpus. A dedicated vector DB is one more service to run,
  back up, and explain; it buys nothing at 10²–10⁴ chunks.
- **Transactional consistency**: chunk text, offsets, metadata, and vectors commit or roll back
  together. No dual-write sync bugs between "content DB" and "vector DB".
- Zero-ops: the whole app state is `backend/data/knowledge.db`. Copy one file to back up.
- Cosine simplifies to a dot product because vectors are L2-normalized at write time, so
  retrieval is one matrix-vector multiply.

Sizing sanity: 512-d float32 ≈ 2 KB/chunk. 10k chunks ≈ 20 MB loaded per query, tens of
milliseconds end to end on a laptop. Comfortable for the assignment's scale; see §7 for the
breaking points.

Rejected alternatives: FAISS (fast, but an index file separate from content, serialization
discipline, and still in-process), Chroma/Qdrant/pgvector (real solutions, unjustified ops
burden here), in-memory-only (loses data on restart: unacceptable for a "knowledge inbox").

## 5. API design decisions

Full contract in [`API.md`](./API.md). Notable choices:

- **One error envelope for everything**: validation, domain, and unexpected errors all return
  `{"error": {code, message, details}}` with a stable machine-readable `code`. Clients branch on
  `code`, not on prose.
- **Status codes that mean something**: 422 validation, 409 duplicate content, 400 invalid or
  blocked URL, 413 oversized page, 415 non-text content, 502 upstream fetch/AI failures.
- **Discriminated union on `type`** for ingest (`note` | `url`) with `extra="forbid"` so typos
  fail loudly instead of silently no-op-ing.
- **Dedupe** by SHA-256 of normalized content. Re-saving the same note/URL returns 409 with the
  existing id instead of silently accumulating duplicates, the common failure of inbox apps.
- **`/query` metadata is part of the response** (`provider`, `model`, `retrieved`, `latency_ms`,
  `warnings`): answer quality is debuggable without server logs.
- **Canned answers without LLM calls** for empty-store and no-retrieval cases: no cost, instant,
  and the message tells the user what to do.
- **`X-Request-ID`** on every response, generated per request or echoed from the caller, ties a
  complaint in the UI to a JSON log line.
- `GET /items/{id}` returns chunks, which makes the chunking visible and verifiable in the UI.

## 6. Debuggability

- **Structured JSON logs to stdout** (`ts`, `level`, `logger`, `message`, `request_id` + context
  fields), one completion line per request (method, path, status, `duration_ms`). No print
  debugging; no PII beyond what the user saved. Uvicorn's own access log is disabled so the
  JSON line is the *only* per-request output; third-party HTTP client loggers are quieted.
- **Request-scoped context** via `contextvars`, so service code can log `request_id` without
  threading it through every signature.
- **Health endpoint** reports provider mode and corpus size (`items`, `chunks`): first thing to
  check when behavior is surprising.
- Validation errors are flattened to `{loc, msg, type}`: stable for clients, no Python reprs.
- 5xx errors log `exc_info`; 4xx log at warning level without stack traces.

## 7. What breaks at scale (honest limits)

| # | Limit | Why | Symptom |
|---|-------|-----|---------|
| 1 | Brute-force cosine is O(N) per query | every query scans all chunks | >~100k chunks: latency grows linearly; p95 in hundreds of ms → seconds |
| 2 | Embeddings loaded per query | rows fetched and decoded each time | memory spikes with corpus size; 100k chunks ≈ 200 MB/query |
| 3 | SQLite single writer | WAL still serializes writes | concurrent ingests queue; heavy write volume blocks |
| 4 | URL fetch inline | synchronous HTTP inside the request | slow/timing-out sites hold a worker; ingest p95 = fetch p95 |
| 5 | LLM call inline | network round trip | query latency = embedding + retrieval + generation; provider hiccups become user-facing 502s |
| 6 | Provider/model switch leaves stale vectors | dimension mismatch is detected, not re-embedded | query warns and skips old chunks until re-ingest |
| 7 | No rate limiting / cost control | open local API | a key + a loop = runaway OpenAI bill |
| 8 | Single-process uvicorn | no horizontal scaling | all traffic on one CPU core; no HA |
| 9 | No HTML fetch cache | re-fetching a URL is a fresh request | duplicate work; remote sites see repeat traffic |
| 10 | No auth / tenant isolation | explicitly out of scope | multi-user or shared deployment is impossible |

Also note: duplicate-chunk overlap means top-k can contain two near-identical chunks; harmless
for the LLM but worth a dedupe/MMR pass at scale.

## 8. Production changes (in priority order)

1. **Auth + per-user scoping**: users table, `user_id` on items, row-level filtering everywhere.
2. **Managed vector store** (pgvector or Qdrant) with HNSW/IVF index; move retrieval out of the
   request process. Migrate embeddings as `vector`/float32 rather than BLOB.
3. **Background ingestion queue** (Celery/RQ/Arq): `POST /ingest` returns 202 + job id; workers
   fetch, chunk, embed, write; retries with backoff; dead-letter on repeated failure.
4. **Streaming answers** (SSE/WebSocket) so long generations are visible immediately.
5. **Hybrid retrieval**: BM25/FTS5 + vectors fused with reciprocal rank fusion, then a
   cross-encoder reranker; dedupe near-identical chunks.
6. **Re-embedding job** triggered by provider/model change, versioned embedding spaces.
7. **Rate limiting + quotas** per user/key; token accounting and cost dashboards; provider
   fallback and circuit breakers.
8. **Observability**: OpenTelemetry traces spanning ingest/retrieve/generate, Prometheus
   metrics (retrieval latency, empty-retrieval rate, token usage), alerting.
9. **Hardening the fetcher**: robots.txt, per-domain politeness/rate limits, fetch cache with
   TTL + ETag, malware/URL reputation checks. Google Docs/Sheets/Slides links are already
   rewritten to their export endpoints (see `fetcher.google_export_url`); other JS-rendered
   pages need a headless renderer.
10. **Ops**: Dockerfile + compose, schema migrations (Alembic), secrets manager, backups of the
    SQLite file (or move to Postgres), CI for tests/lint/build.
11. **Answer quality**: context-window budgeting per model, citation validation (verify the
     answer only cites retrieved indices), prompt/version A/B evaluation harness, feedback thumbs.
12. **Security**: tighten CORS, CSP, sanitize rendered content, encrypt at rest, request
    size limits at the edge.

## 9. Security notes (what is covered here)

- **SSRF guard** on URL ingest: resolves the host and rejects loopback/private/link-local/
  reserved/unspecified addresses unless explicitly enabled (`ALLOW_PRIVATE_URLS`), plus size and
  content-type caps. Not airtight (DNS rebinding), but blocks the obvious `http://127.0.0.1` and
  internal-metadata probes; a production fetcher should pin the resolved IP and run sandboxed.
- **XSS**: React escapes all rendered content; the app never uses `dangerouslySetInnerHTML`.
- **No secrets in logs**: provider errors are sanitized before surfacing; the API key is only
  read from env.
- **Input limits** at the schema level (content 100k chars, URL 2k, question 1k).

## 10. Testing strategy

- Unit: chunking invariants (never empty, never over limit, overlap present, coverage),
  vector search ordering/dimension filtering, store cascade deletes.
- API: full ingest → list → detail → query flow against a tmp SQLite DB with the **offline
  provider injected** (deterministic, no network), fetcher monkeypatched for URL paths, plus
  the error matrix (422/404/409/400/502/415/413).
- Frontend: TypeScript build as the static gate; end-to-end smoke through a real browser against
  the running API (add note → list → ask → citations → delete).
