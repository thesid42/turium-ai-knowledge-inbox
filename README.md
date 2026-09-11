# Turium — AI Knowledge Inbox

A minimal, production-style RAG app: save short notes and URLs, then ask questions over
everything you've saved. Answers come from your own content and cite the exact source chunks.

Built for the [assignment brief](./Turium_AI_Interview_Assignment.pdf) with FastAPI + SQLite on
the backend and React + Tailwind on the frontend.

## Features

- **Ingest** plain-text notes or URLs (server-side fetch, HTML→text extraction; Google
  Docs/Sheets/Slides links are auto-exported to plain text instead of the JS shell)
- **Semantic search + RAG**: structure-aware chunking → embeddings → vector search → grounded
  answer with numbered citations
- **Works with zero setup**: deterministic offline provider (hashed lexical embeddings +
  extractive answers) so the whole pipeline runs without an API key
- **Upgrades to OpenAI** by setting one env var — same pipeline, same API
- Structured JSON logs, consistent error envelope, `X-Request-ID` tracing, input validation
- Duplicate detection (409), SSRF guard on URL ingest, size/content-type caps

## Quickstart

Prerequisites: Python 3.12+, Node 20+.

### 1. Backend (terminal 1)

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Runs at `http://localhost:8000`. Check `GET /health` — without configuration it reports
`"provider": "offline"` and the app is fully usable.

### 2. Frontend (terminal 2)

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to the backend.

### 3. Optional: enable a hosted provider

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

> Verified against OpenRouter with `nvidia/nemotron-3-super-120b-a12b:free` (fast, follows the
> grounded prompt, clean refusals). If it is temporarily rate-limited, try
> `nex-agi/nex-n2.5-pro:free` or any other `:free` model from `GET /api/v1/models`.

Restart the backend. `/health` will report `"provider": "openai"` with the configured
embedding/chat models. Restart the frontend to pick up the provider badge.

> Switching providers changes the embedding space: previously ingested chunks are skipped with a
> warning until re-ingested. See [Design notes](./docs/DESIGN.md) §3.

## Configuration

All settings are environment variables (see [`backend/.env.example`](./backend/.env.example)).
The most useful ones:

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `auto` | `auto` \| `openai` \| `offline` |
| `OPENAI_API_KEY` | — | enables OpenAI when present |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | hosted embedding model |
| `CHAT_MODEL` | `gpt-4o-mini` | hosted answer model |
| `DB_PATH` | `./data/knowledge.db` | SQLite file (content + vectors) |
| `CHUNK_MAX_CHARS` / `CHUNK_OVERLAP_CHARS` | `1000` / `150` | chunking knobs |
| `FETCH_MAX_BYTES` / `FETCH_TIMEOUT_SECONDS` | `5000000` / `10` | URL fetch limits |
| `ALLOW_PRIVATE_URLS` | `false` | disable the SSRF guard (local testing only) |
| `LOG_LEVEL` | `INFO` | structured JSON log verbosity |

## API

Documented in [`docs/API.md`](./docs/API.md). Smoke test:

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
```

## Project layout

```
backend/
  app/
    main.py            # app factory, lifespan, middleware
    config.py          # pydantic-settings
    logging_config.py  # JSON logs + request-id context
    errors.py          # error envelope + handlers
    schemas.py         # request/response models
    db.py / store.py   # SQLite schema, CRUD, vector search
    routers/           # health, ingest, items, query
    services/          # chunking, fetcher, rag
    providers/         # offline + openai, selected by factory
  tests/
frontend/
  src/
    api/client.ts      # typed API client
    hooks/             # useItems, useQuery, useHealth
    components/        # IngestForm, ItemList, QueryPanel, AnswerCard, …
docs/
  API.md               # HTTP contract with examples
  DESIGN.md            # tradeoffs, scaling limits, production changes
  SPEC.md              # frozen implementation spec used to build this
```

## Design decisions at a glance

The full reasoning, failure modes, and production upgrade path are in
[`docs/DESIGN.md`](./docs/DESIGN.md). Summary:

- **Chunking**: paragraph/sentence-aware packing at ~1000 chars with 150-char word-boundary
  overlap — cheap, deterministic, structure-preserving, testable offline.
- **Vector store**: float32 embeddings in the same SQLite file as content, brute-force cosine
  with numpy. Transactional consistency and zero ops at this scale; comfortable to ~10k chunks.
- **Providers**: one interface, two implementations (OpenAI and offline), selected by env —
  the app never requires a key to be demoed, and never fakes semantic quality in offline mode.
- **What breaks at scale**: O(N) retrieval, per-query embedding loads, single-writer SQLite,
  inline fetch and LLM calls. Each has a documented production fix (pgvector/Qdrant + HNSW,
  background ingest queue, streaming answers, hybrid retrieval).
