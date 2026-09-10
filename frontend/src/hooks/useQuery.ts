/**
 * Hook for querying the RAG pipeline with ask and reset operations.
 */

import { useCallback, useRef, useState } from 'react';
import { query as queryApi } from '../api/client';
import type { QueryRequest, QueryResponse, Citation } from '../types';

interface UseQueryReturn {
  answer: string | null;
  citations: Citation[];
  provider: string | null;
  model: string | null;
  warnings: string[];
  loading: boolean;
  error: Error | null;
  ask: (request: QueryRequest) => Promise<void>;
  reset: () => void;
}

export function useQuery(): UseQueryReturn {
  const [answer, setAnswer] = useState<string | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [provider, setProvider] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Track the current request to ignore stale responses - useRef to persist across renders
  const requestIdRef = useRef(0);

  const ask = useCallback(async (request: QueryRequest) => {
    setLoading(true);
    setError(null);
    // Don't clear previous answer/citations until new one arrives

    const currentRequestId = ++requestIdRef.current;

    try {
      const response: QueryResponse = await queryApi(request);

      // Ignore stale responses
      if (currentRequestId !== requestIdRef.current) {
        return;
      }

      setAnswer(response.answer);
      setCitations(response.citations);
      setProvider(response.provider);
      setModel(response.model);
      setWarnings(response.warnings);
    } catch (err) {
      if (currentRequestId !== requestIdRef.current) {
        return;
      }
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const reset = useCallback(() => {
    requestIdRef.current += 1; // Invalidate any in-flight requests
    setAnswer(null);
    setCitations([]);
    setProvider(null);
    setModel(null);
    setWarnings([]);
    setError(null);
    setLoading(false);
  }, []);

  return {
    answer,
    citations,
    provider,
    model,
    warnings,
    loading,
    error,
    ask,
    reset,
  };
}