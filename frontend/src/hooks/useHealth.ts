/**
 * Hook for fetching health/provider info once on mount.
 */

import { useEffect, useState } from 'react';
import { getHealth } from '../api/client';
import type { HealthResponse } from '../types';

export function useHealth() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let mounted = true;

    async function fetchHealth() {
      try {
        const result = await getHealth();
        if (mounted) {
          setData(result);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    fetchHealth();

    return () => {
      mounted = false;
    };
  }, []);

  return { data, loading, error };
}