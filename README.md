# Turium — AI Knowledge Inbox

Save short notes and URLs, then ask questions over everything you've saved. Answers are grounded
in your own content and cite the exact source chunks.

FastAPI + SQLite on the backend, React + Tailwind on the frontend.

## Features

- **Ingest notes and URLs** — server-side fetch with HTML→text extraction; Google
  Docs/Sheets/Slides links are auto-exported to text (the document must be shared as
  "Anyone with the link")
- **Ask questions over your content** — chunking → embeddings → vector search → grounded answer
  with numbered citations, rendered with markdown formatting
- **Runs with zero setup** — deterministic offline provider (keyword-based embeddings +
  extractive answers) works without any API key
- **Upgrades to OpenAI or any OpenAI-compatible gateway** (e.g. OpenRouter) with a few
  environment variables
- **Safe by default** — input validation, duplicate detection, SSRF guard on URL ingest, fetch
  size/content-type limits, and clear errors for private or JavaScript-only pages

## Quickstart

Prerequisites: Python 3.12+, Node 20+.

### 1. Backend (terminal 1)

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Runs at `http://localhost:8000` — without configuration it reports `"provider": "offline"` at
`GET /health` and is fully usable.

### 2. Frontend (terminal 2)

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to the backend.

### 3. Use a hosted model (optional)

Any OpenAI-compatible API works. Copy the example env file and edit it:

```powershell
cd backend
Copy-Item .env.example .env
```

**OpenAI:**

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

**OpenRouter (works with a free model, no billing needed):**

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=sk-or-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_MODEL=openai/text-embedding-3-small
CHAT_MODEL=nvidia/nemotron-3-super-120b-a12b:free
```

Restart the backend afterwards; `/health` reports the active provider and models.

## Configuration

All settings are environment variables (see [`backend/.env.example`](./backend/.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `auto` | `auto` \| `openai` \| `offline` |
| `OPENAI_API_KEY` | — | enables OpenAI when present |
| `OPENAI_BASE_URL` | — | OpenAI-compatible base URL (OpenRouter, Azure, proxies) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | hosted embedding model |
| `CHAT_MODEL` | `gpt-4o-mini` | hosted answer model |
| `DB_PATH` | `./data/knowledge.db` | SQLite file (content + vectors) |
| `CHUNK_MAX_CHARS` / `CHUNK_OVERLAP_CHARS` | `1000` / `150` | chunking knobs |
| `FETCH_MAX_BYTES` / `FETCH_TIMEOUT_SECONDS` | `5000000` / `10` | URL fetch limits |
| `FETCH_USER_AGENT` | browser-like + contact URL | UA sent on fetches |
| `ALLOW_PRIVATE_URLS` | `false` | disable the SSRF guard (local testing only) |
| `LOG_LEVEL` | `INFO` | log verbosity |

## API

Full contract with examples: [`docs/API.md`](./docs/API.md).

```powershell
curl http://localhost:8000/health
curl -X POST http://localhost:8000/ingest -H "Content-Type: application/json" `
  -d '{"type":"note","content":"Postgres uses MVCC for concurrency control.","title":"DB notes"}'
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" `
  -d '{"question":"How does Postgres handle concurrency?"}'
```

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q     # unit + API tests, offline and deterministic

cd ..\frontend
npm run build                            # TypeScript + Vite production build
npm run lint                             # oxlint
```

## Design decisions and tradeoffs

- **Chunking: ~1000 chars, 150-char overlap, paragraph/sentence-aware.** Structure-aware splits
  keep chunks coherent, and the overlap preserves context that straddles a boundary. Tradeoff:
  fixed-size windows are simpler but cut sentences; semantic chunking costs an LLM pass per item
  and can't be tested offline. Chunks are exact slices of the normalized text, so citation
  offsets are always accurate and no content is dropped.
- **Embeddings: OpenAI `text-embedding-3-small`, with a deterministic offline fallback.** Real
  semantic quality when a key exists; keyword hashing keeps the app fully runnable (and tests
  deterministic) without one. Tradeoff: offline mode is lexical, not semantic — labelled as such
  in the UI.
- **Vector store: SQLite + in-process numpy cosine.** Content and vectors commit in one
  transaction (no dual-write bugs), zero extra infra, one-file backup. Brute-force scan is
  milliseconds at this scale; tradeoff: O(N) retrieval with no ANN index — the point where
  pgvector/Qdrant + HNSW would take over.
- **Provider abstraction (one interface, two implementations).** Switching providers or pointing
  at any OpenAI-compatible gateway (OpenRouter, Azure) is environment config only. Tradeoff:
  embedding spaces differ per model, so chunks from a different provider are skipped with a
  warning until re-ingested.
- **Grounded answers with citations; no LLM call when retrieval is empty.** Answers use only
  retrieved chunks and carry numbered sources; empty or irrelevant queries return a canned
  response instantly. Tradeoff: strict grounding makes the model refuse rather than improvise.
- **Synchronous, single-service design.** FastAPI, SQLite, inline fetch/LLM calls — simple to run
  and debug. Tradeoff: those are the scaling bottlenecks later (queue, streaming, horizontal
  scaling); the full list and production path is in [`docs/DESIGN.md`](./docs/DESIGN.md).

## Documentation

- [`docs/API.md`](./docs/API.md) — HTTP contract, error codes, examples
- [`docs/DESIGN.md`](./docs/DESIGN.md) — chunking rationale, vector store choice, scaling limits,
  production changes
- [`docs/SPEC.md`](./docs/SPEC.md) — implementation spec this build followed
