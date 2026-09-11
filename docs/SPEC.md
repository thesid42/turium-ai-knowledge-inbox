# Turium — Implementation Specification (v1, frozen)

Internal build spec for the AI Knowledge Inbox assignment. This is the contract the
implementation workers must follow. Do not change API shapes, error codes, file layout,
or algorithms without checking with the architect first.

## 1. Goal

Single-user web app:

1. Save short notes (plain text) and URLs (server-side fetch).
2. Ask natural-language questions over saved content.
3. Answers come from a RAG pipeline: chunk -> embed -> store -> retrieve -> LLM answer with cited sources.

Deliverable quality bar: production-style structure, structured logging, consistent error
envelope, intentional chunking, debuggability, no god files.

## 2. Stack

- Backend: Python 3.12 + FastAPI + uvicorn, SQLite (stdlib `sqlite3`), numpy for cosine,
  httpx + beautifulsoup4 for URL fetching, `openai` SDK for the hosted provider.
- Frontend: Vite + React 19 + TypeScript + Tailwind CSS v4 + plain hooks (no state library).
- No auth. Single user. No Docker/K8s.

## 3. Repository layout

```
Turium/
├── .gitignore
├── README.md                      # architect-owned
├── docs/
│   ├── SPEC.md                    # this file
│   ├── DESIGN.md                  # architect-owned (tradeoffs)
│   └── API.md                     # architect-owned (contract)
├── backend/                       # worker A
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── .env.example
│   ├── pytest.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # create_app(), module-level app, lifespan, middleware wiring
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── logging_config.py      # JSON formatter + request_id contextvar
│   │   ├── errors.py              # AppError + exception handlers + error envelope
│   │   ├── schemas.py             # all Pydantic request/response models
│   │   ├── db.py                  # connection helper + schema DDL
│   │   ├── store.py               # items+chunks CRUD, embeddings persistence, cosine search
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── ingest.py
│   │   │   ├── items.py
│   │   │   └── query.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── chunking.py
│   │   │   ├── fetcher.py
│   │   │   └── rag.py             # retrieve -> citations -> provider answer
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py            # protocols + DTOs
│   │       ├── offline.py         # deterministic hashed embeddings + extractive answers
│   │       ├── openai_provider.py
│   │       └── factory.py         # provider selection from Settings
│   └── tests/
│       ├── conftest.py
│       ├── test_chunking.py
│       ├── test_store.py
│       ├── test_ingest_api.py
│       ├── test_items_api.py
│       ├── test_query_api.py
│       └── test_errors.py
└── frontend/                      # worker B
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
    ├── index.html
    ├── .env.example
    └── src/
        ├── main.tsx
        ├── index.css
        ├── App.tsx
        ├── types.ts
        ├── api/client.ts
        ├── hooks/useHealth.ts
        ├── hooks/useItems.ts
        ├── hooks/useQuery.ts
        └── components/
            ├── Header.tsx
            ├── IngestForm.tsx
            ├── ItemList.tsx
            ├── ItemRow.tsx
            ├── QueryPanel.tsx
            ├── AnswerCard.tsx
            └── ui.tsx          # tiny shared primitives: Badge, Spinner, ErrorBanner, EmptyState
```

Rules: no file above ~250 lines; no copy-paste; type hints everywhere in Python; no `Any`
in TypeScript except at validated API boundaries.

## 4. Configuration (backend)

`app/config.py`, pydantic-settings, reads `backend/.env` if present, env var names exactly:

| Var | Default | Notes |
|---|---|---|
| `AI_PROVIDER` | `auto` | `auto` \| `openai` \| `offline` |
| `OPENAI_API_KEY` | unset | when set and provider=auto -> openai |
| `OPENAI_BASE_URL` | unset | pass to SDK only if set (OpenAI-compatible gateways) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | |
| `CHAT_MODEL` | `gpt-4o-mini` | |
| `DB_PATH` | `./data/knowledge.db` | relative to backend working dir; parent auto-created |
| `CHUNK_MAX_CHARS` | `1000` | |
| `CHUNK_OVERLAP_CHARS` | `150` | |
| `CHUNK_MIN_CHARS` | `50` | |
| `FETCH_TIMEOUT_SECONDS` | `10` | |
| `FETCH_MAX_BYTES` | `5000000` | |
| `ALLOW_PRIVATE_URLS` | `false` | SSRF guard toggle (tests may enable) |
| `DEFAULT_TOP_K` | `5` | |
| `MAX_TOP_K` | `20` | |
| `OFFLINE_EMBEDDING_DIM` | `512` | |
| `LOG_LEVEL` | `INFO` | |

`Settings` fields are snake_case (`db_path`, ...). `get_settings()` is `lru_cache`d for the
module-level app; `create_app(settings=...)` accepts an explicit instance for tests.

## 5. Storage

SQLite, WAL mode, `foreign_keys=ON`, `row_factory=sqlite3.Row`. One connection per request
(cheap), opened via context manager in `db.py`. Schema created on startup (idempotent).

```sql
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('note','url')),
  title TEXT,
  source TEXT,                        -- canonical URL for type=url, else NULL
  raw_content TEXT NOT NULL,
  content_hash TEXT NOT NULL,         -- sha256 hex of normalized content
  created_at TEXT NOT NULL,           -- ISO 8601 UTC
  char_count INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_content_hash ON items(content_hash);

CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  char_start INTEGER NOT NULL,
  char_end INTEGER NOT NULL,
  embedding BLOB NOT NULL,            -- float32 little-endian, L2-normalized
  embedding_dim INTEGER NOT NULL,
  embedding_model TEXT NOT NULL,
  embedding_provider TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_item_id ON chunks(item_id);
```

`store.py` exposes: `init_schema(conn)`, `insert_item_with_chunks(...)` (single transaction),
`list_items(conn, limit, offset) -> (rows, total)`, `get_item(conn, id)`, `get_item_chunks(conn, id)`,
`delete_item(conn, id) -> bool`, `count_items/count_chunks(conn)`,
`search(conn, query_embedding: list[float], top_k) -> list[ScoredChunk]`,
`count_mismatched_chunks(conn, dim) -> int`.
`ScoredChunk` = dataclass(chunk_id, item_id, chunk_index, content, char_start, char_end, title,
source, item_type, score). Search: filter `embedding_dim = len(query)`, cosine = dot product of
L2-normalized vectors (numpy), return top_k by score; zero query vector -> [].

## 6. Chunking (`services/chunking.py`)

Deterministic, character-based (cheap, language-agnostic, good enough for mixed notes/URLs).

1. Normalize: `\r\n -> \n`, collapse 3+ newlines to 2, strip trailing spaces per line, strip.
2. If `len(text) <= max_chars` -> one chunk spanning the whole text.
3. Split on blank lines (`\n\n`) into paragraphs. Greedily pack paragraphs into a chunk while
   `len(chunk) + 2 + len(paragraph) <= max_chars`.
4. Oversized paragraph: split into sentences (`re.split(r'(?<=[.!?])\s+', p)`), pack sentences
   the same way. Oversized single sentence: hard-split at word boundaries (never mid-word).
5. Overlap: when a new chunk starts, prepend the last `overlap_chars` of the previous chunk,
   trimmed to the next word boundary; only if the result still fits `max_chars`.
6. Merge a trailing chunk into the previous one when its trimmed length `< min_chars`.
7. Return `list[ChunkDraft(content, char_start, char_end)]` where offsets refer to the normalized
   text. Empty/whitespace-only input -> `[]`.

Invariants (tested): never empty chunks; no chunk exceeds `max_chars`; concatenated content
covers all non-whitespace input; consecutive chunks share overlap when possible.

## 7. URL fetching (`services/fetcher.py`)

`fetch_url(url, settings) -> FetchedPage(title, text, final_url)` using sync `httpx.Client`
(`follow_redirects=True`, timeout from settings, UA from `FETCH_USER_AGENT`; sites like Wikipedia
reject UAs without contact info, so the default includes a `+URL` contact token).

Validation/errors (all `AppError`):
- scheme must be http/https else `INVALID_URL` (400).
- resolve hostname via `socket.getaddrinfo`; reject loopback/private/link-local/reserved/unspecified
  IPs unless `allow_private_urls` -> `BLOCKED_URL` (400). Also `localhost` blocked.
- non-2xx upstream -> `FETCH_FAILED` (502) with status in details.
- `Content-Type` must be `text/html` or `text/plain` -> else `UNSUPPORTED_CONTENT_TYPE` (415).
- stream body, abort past `FETCH_MAX_BYTES` -> `CONTENT_TOO_LARGE` (413).

HTML -> text: BeautifulSoup `html.parser`; drop `script,style,noscript,header,footer,nav,form,svg,iframe`;
pick `<article>` / `<main>` / `[role=main]` / `body` (first present); text via `get_text("\n", strip=True)`;
title from `<title>`, else first `<h1>`, else hostname. Single newlines from inline tags are
collapsed to spaces. `text/plain`: body as-is (utf-8-sig decode).

Google Docs/Sheets/Slides links (`docs.google.com/{document,spreadsheets,presentation}/d/<id>`)
are rewritten to export endpoints (`.txt` / `.csv`) before fetching; the original URL is kept as
`source`, the first line of a text export becomes the title, and an HTML response to an export
request (private doc) fails with a clear `FETCH_FAILED` instead of indexing a shell page.
`text/csv` is an accepted content type. Short pages matching the browser-support shell marker
fail loudly rather than indexing garbage.

## 8. Providers (`app/providers/`)

`base.py`:

```python
@dataclass
class RetrievedChunk:      # same as ScoredChunk, used by chat providers
    citation_index: int
    content: str
    title: str | None
    source: str | None
    item_type: str
    score: float

class EmbeddingProvider(Protocol):
    name: str; model: str; dimension: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class ChatProvider(Protocol):
    name: str; model: str
    def answer(self, question: str, sources: list[RetrievedChunk]) -> str: ...
```

`factory.build_providers(settings) -> (EmbeddingProvider, ChatProvider)`:
`auto` -> openai when key present, else offline (log which was chosen at INFO).

`offline.py`:
- `OfflineEmbeddingProvider(dimension=512)`: tokens `re.findall(r"[a-z0-9']+", text.lower())`;
  stable per-token hash with `hashlib.blake2b(token.encode(), digest_size=8)` (never Python `hash`);
  **sparse signed hashing**: each token maps to one dimension (`h % dim`) with a sign bit taken
  from the hash, so texts with disjoint vocabularies have cosine exactly 0; accumulate
  `1 + ln(tf)` weight per token; L2 normalize; empty input -> zero vector.
  `name="offline"`, `model=f"offline-hashing-{dim}"`. Docstring states plainly: lexical, not semantic.
- `OfflineChatProvider(embedding_provider)`: split each source chunk into sentences
  (`re.split(r'(?<=[.!?])\s+', ...)`), embed sentences + question, score cosine, keep up to 4
  sentences with `score >= max(0.05, 0.5 * best_score)`, dedupe identical, return them joined as
  a short answer with `[k]` markers matching citation index. If best score <= 0 or no sources:
  `"I couldn't find anything relevant in your saved items. (Offline mode uses keyword matching — set OPENAI_API_KEY for semantic answers.)"`
  `name="offline"`, `model="offline-extractive"`.

`openai_provider.py`: `OpenAIEmbeddingProvider` batches inputs (<= 100 per call, preserve order);
`OpenAIChatProvider` builds a grounded prompt:
system = "You are a knowledge assistant. Answer ONLY from the user's saved content below.
Cite every claim with bracketed source numbers, e.g. [1]. If the answer is not in the content,
say you couldn't find it in the saved items. Be concise."
user = numbered blocks `[k] (title — source)\ncontent` then `Question: ...`. temperature 0.2.
Responses are post-processed with `normalize_citations()` so provider-specific glyphs
(`【1†L1-L4】`, `[1†L1-L2]`) become `[1]`.
Errors from the SDK -> `AppError("UPSTREAM_AI_ERROR", 502)` with sanitized message (no key leakage).

## 9. RAG (`services/rag.py`)

`answer_question(store_ctx, question, top_k, embedder, chat, settings) -> QueryResult`:
1. `question_vec = embedder.embed([question])[0]`.
2. `scored = store.search(...)` — chunks with cosine `<= 0` are dropped (no overlap = no retrieval).
3. If no chunks at all -> canned answer `"You haven't saved anything yet — add a note or URL first."` + no citations, no LLM call.
4. If retrieval empty (zero vector / no match) -> canned `"I couldn't find anything relevant in your saved items."`, citations [].
5. Else build citations (index 1..n) and call `chat.answer`.
6. `warnings`: if `count_mismatched_chunks(dim) > 0` -> "N chunks were embedded with a different model and were skipped; re-ingest content after changing the AI provider."
7. `QueryResult(answer, citations, provider=chat.name, model=chat.model, retrieved=len(scored), latency_ms, warnings)`.

## 10. HTTP API (contract — frozen)

Error envelope (all errors, including validation):

```json
{ "error": { "code": "FETCH_FAILED", "message": "human readable", "details": {"...": "..."} } }
```

Codes: `VALIDATION_ERROR` 422, `NOT_FOUND` 404, `DUPLICATE_ITEM` 409, `INVALID_URL` 400,
`BLOCKED_URL` 400, `UNSUPPORTED_CONTENT_TYPE` 415, `CONTENT_TOO_LARGE` 413,
`FETCH_FAILED` 502, `UPSTREAM_AI_ERROR` 502, `INTERNAL_ERROR` 500.

Every response carries `X-Request-ID` (uuid4 hex generated per request, or echoed from the
incoming header if provided).

### `GET /health` -> 200
```json
{ "status": "ok", "provider": "offline", "chat_model": "offline-extractive",
  "embedding_model": "offline-hashing-512", "items": 2, "chunks": 7 }
```

### `POST /ingest` -> 201
Discriminated union on `type` (`extra="forbid"`):
```json
{ "type": "note", "content": "text", "title": "optional" }
{ "type": "url",  "url": "https://example.com", "title": "optional override" }
```
`content` 1..100000 chars (after strip -> else 422); `title` <= 200; `url` <= 2048.
Response:
```json
{ "item": { "id": "ab12…", "type": "note", "title": null, "source": null,
            "created_at": "2026-09-10T12:00:00+00:00", "char_count": 412, "chunk_count": 1 },
  "chunks_created": 1 }
```
Duplicate content hash (normalized) -> 409 `DUPLICATE_ITEM` with `details.item_id`.
Empty content after normalization (e.g. URL page with no text) -> 422 `VALIDATION_ERROR`.

### `GET /items?limit=50&offset=0` -> 200
`limit` 1..100, `offset` >= 0. Newest first (`created_at DESC, id DESC`).
```json
{ "items": [ { "id": "…", "type": "url", "title": "…", "source": "https://…",
               "created_at": "…", "char_count": 8123, "chunk_count": 9 } ],
  "total": 12, "limit": 50, "offset": 0 }
```

### `GET /items/{id}` -> 200 / 404
```json
{ "item": { …summary… }, "chunks": [ { "id": "…", "chunk_index": 0, "content": "…",
  "char_start": 0, "char_end": 800, "embedding_model": "offline-hashing-512" } ] }
```

### `DELETE /items/{id}` -> 204 (cascades chunks) / 404

### `POST /query` -> 200
```json
{ "question": "what did I save about X?", "top_k": 5 }
```
`question` 1..1000 (trimmed, non-empty); `top_k` 1..20 default `DEFAULT_TOP_K`.
```json
{ "answer": "… [1] …",
  "citations": [ { "index": 1, "item_id": "…", "chunk_id": "…", "title": "…",
                   "source": null, "type": "note", "snippet": "first 240 chars…", "score": 0.82 } ],
  "provider": "offline", "model": "offline-extractive", "retrieved": 3,
  "latency_ms": 12, "warnings": [] }
```

## 11. Cross-cutting backend behavior

- **Structured logging**: JSON lines to stdout: `ts`, `level`, `logger`, `message`, `request_id`,
  plus extras (method, path, status, duration_ms, provider, item_id, ...). One middleware logs each
  request completion; uvicorn's plain-text access log is disabled to avoid duplicate lines.
  Errors log with `exc_info` for 5xx only.
- **Validation**: pydantic models, `extra="forbid"`. `RequestValidationError` handler flattens to
  `details.errors = [{loc, msg, type}]` (no Python reprs).
- **Endpoints are sync `def`** (FastAPI threadpool); pipeline is blocking by design.
- **CORS**: permissive for local dev (`["*"]`), documented as a production change.
- **Tests**: pytest + `fastapi.testclient.TestClient`; every test uses a tmp DB and injected
  offline providers (no network); fetcher monkeypatched for URL tests. No sleeps. Deterministic.

## 12. Frontend contract

- Dev proxy: `/api/*` -> `http://localhost:8000/*` (rewrite strips `/api`). `src/api/client.ts`
  uses base `/api`; typed helpers return parsed JSON or throw `ApiError(status, code, message, details)`.
- Types in `src/types.ts` mirror section 10 exactly (snake_case fields).
- `useItems`: `{ items, total, loading, error, refresh, ingest, remove }`; `ingest` returns the
  created item; list refetches after ingest; delete removes locally on 204.
- `useQuery`: `{ answer, citations, provider, model, warnings, loading, error, ask, reset }`.
- `useHealth`: provider badge data, fetched once on mount.
- `App` layout: header; 2-column grid on `lg` (left: ingest form + item list; right: question panel
  + answer), single column on mobile. Light theme, slate/indigo, cards `rounded-xl border`,
  focus rings, disabled states, loading spinners, friendly empty states, inline error banners that
  show `error.message` from the envelope.
- `IngestForm`: Note/URL toggle; textarea or URL input; client-side non-empty check; success line
  with chunks created; server errors surfaced verbatim.
- `ItemRow`: type badge, title (fallback "Untitled note" / URL hostname), date (`toLocaleString`),
  `n chunks`, delete button with confirm; click expands -> fetches `GET /items/{id}` once and shows
  numbered chunk previews (mono, truncated). Source URLs open in a new tab.
- `QueryPanel`: question input + Ask button; loading state; disabled when empty.
- `AnswerCard`: answer text rendered as markdown via `react-markdown` (Tailwind-mapped
  paragraphs, lists, headings, code, links, quotes; raw HTML disabled), provider/model footer,
  warnings banner, numbered citation cards (index badge, title/source link, quoted snippet,
  score to 2 dp).
- Accessibility basics: labels, `aria-busy` on loading regions, buttons have discernible text.
- No router, no Redux, no shadcn, no extra UI deps beyond Tailwind.

## 13. Acceptance criteria

Backend (run from `backend/`):
```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest -q          # all green
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Then: `/health` 200; note ingest 201; duplicate 409; URL ingest against a real page 201; query
returns answer + citations; `127.0.0.1` URL -> 400; bad payload -> 422 envelope.

Frontend (run from `frontend/`):
```
npm install
npm run build          # tsc + vite build, zero errors
npm run dev            # http://localhost:5173 with backend running
```
Manual smoke: add note -> appears listed; ask question -> answer + cited snippets; add URL ->
listed; delete -> disappears; provider badge reflects `/health`.

## 14. Out of scope (documented as production changes in DESIGN.md)

Auth, multi-user isolation, hybrid/BM25 search, reranker, streaming answers, background ingest
queue, rate limiting, Docker, pgvector/Qdrant, re-index endpoint, observability stack.
