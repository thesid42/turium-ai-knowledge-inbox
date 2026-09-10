/**
 * Typed API client with request wrapper and endpoint functions.
 * Base path is '/api' which is proxied to http://localhost:8000 in dev.
 */

import type {
  ItemDetail,
  ItemsResponse,
  IngestRequest,
  IngestResponse,
  QueryRequest,
  QueryResponse,
  HealthResponse,
  ApiErrorBody,
} from '../types';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | undefined;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type');
  const isJson = contentType?.includes('application/json');

  let data: unknown;
  if (isJson) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    let code = 'INTERNAL_ERROR';
    let message = response.statusText || 'Request failed';
    let details: Record<string, unknown> | undefined;

    if (isJson && typeof data === 'object' && data !== null && 'error' in data) {
      const errorBody = data as ApiErrorBody;
      code = errorBody.error?.code ?? code;
      message = errorBody.error?.message ?? message;
      details = errorBody.error?.details;
    } else if (typeof data === 'string') {
      message = data;
    }

    throw new ApiError(response.status, code, message, details);
  }

  return data as T;
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

export async function listItems(limit = 50, offset = 0): Promise<ItemsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request<ItemsResponse>(`/items?${params.toString()}`);
}

export async function getItem(id: string): Promise<ItemDetail> {
  return request<ItemDetail>(`/items/${encodeURIComponent(id)}`);
}

export async function deleteItem(id: string): Promise<void> {
  return request<void>(`/items/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export async function ingest(requestBody: IngestRequest): Promise<IngestResponse> {
  return request<IngestResponse>('/ingest', {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
}

export async function query(requestBody: QueryRequest): Promise<QueryResponse> {
  return request<QueryResponse>('/query', {
    method: 'POST',
    body: JSON.stringify(requestBody),
  });
}