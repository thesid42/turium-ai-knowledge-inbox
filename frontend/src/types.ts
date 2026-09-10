/**
 * Type definitions mirroring the frozen HTTP API contract (SPEC section 10).
 * All fields are snake_case as returned by the backend.
 */

export interface Item {
  id: string;
  type: 'note' | 'url';
  title: string | null;
  source: string | null;
  created_at: string;
  char_count: number;
  chunk_count: number;
}

export interface Chunk {
  id: string;
  chunk_index: number;
  content: string;
  char_start: number;
  char_end: number;
  embedding_model: string;
}

export interface ItemDetail {
  item: Item;
  chunks: Chunk[];
}

export interface IngestRequestNote {
  type: 'note';
  content: string;
  title?: string;
}

export interface IngestRequestUrl {
  type: 'url';
  url: string;
  title?: string;
}

export type IngestRequest = IngestRequestNote | IngestRequestUrl;

export interface IngestResponse {
  item: Item;
  chunks_created: number;
}

export interface ItemsResponse {
  items: Item[];
  total: number;
  limit: number;
  offset: number;
}

export interface QueryRequest {
  question: string;
  top_k?: number;
}

export interface Citation {
  index: number;
  item_id: string;
  chunk_id: string;
  title: string | null;
  source: string | null;
  type: 'note' | 'url';
  snippet: string;
  score: number;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  provider: string;
  model: string;
  retrieved: number;
  latency_ms: number;
  warnings: string[];
}

export interface HealthResponse {
  status: string;
  provider: string;
  chat_model: string;
  embedding_model: string;
  items: number;
  chunks: number;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export type ItemType = 'note' | 'url';