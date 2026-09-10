/**
 * Hook for managing the items list with refresh, ingest, and remove operations.
 */

import { useCallback, useState } from 'react';
import { listItems, ingest as ingestApi, deleteItem } from '../api/client';
import type { Item, ItemsResponse, IngestRequest, IngestResponse } from '../types';

export function useItems() {
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response: ItemsResponse = await listItems();
      setItems(response.items);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  const ingest = useCallback(async (request: IngestRequest): Promise<IngestResponse> => {
    setError(null);
    const response = await ingestApi(request);
    // Refresh the list after successful ingest
    await refresh();
    return response;
  }, [refresh]);

  const remove = useCallback(async (id: string): Promise<void> => {
    setError(null);
    await deleteItem(id);
    // Optimistic removal
    setItems((prev) => prev.filter((item) => item.id !== id));
    setTotal((prev) => prev - 1);
  }, []);

  return {
    items,
    total,
    loading,
    error,
    refresh,
    ingest,
    remove,
  };
}