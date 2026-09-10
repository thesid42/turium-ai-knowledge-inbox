/**
 * ItemList component for displaying the list of saved items.
 * Presentational component - receives all data and callbacks as props.
 */

import { ItemRow } from './ItemRow';
import { Spinner, EmptyState, ErrorBanner } from './ui';
import type { Item } from '../types';

interface ItemListProps {
  items: Item[];
  total: number;
  loading: boolean;
  error: Error | null;
  onRefresh: () => void;
  onRemove: (id: string) => Promise<void>;
}

export function ItemList({ items, total, loading, error, onRefresh, onRemove }: ItemListProps) {
  if (loading && items.length === 0) {
    return (
      <section className="card" aria-busy="true" aria-label="Loading items">
        <div className="p-8 flex flex-col items-center gap-4">
          <Spinner size="lg" />
          <p className="text-slate-500">Loading your knowledge base…</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="card" aria-live="polite">
        <div className="p-6">
          <ErrorBanner message={error.message} onDismiss={onRefresh} />
        </div>
      </section>
    );
  }

  return (
    <section className="card" aria-labelledby="items-heading">
      <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 id="items-heading" className="text-lg font-semibold text-slate-900">
          Saved Items
          <span className="ml-2 text-sm font-normal text-slate-500">({total} total)</span>
        </h2>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="btn-ghost text-sm"
          aria-label="Refresh list"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {items.length === 0 ? (
        <div className="p-8">
          <EmptyState
            icon={
              <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            }
            title="No items yet"
            description="Add a note or URL to start building your knowledge base."
          />
        </div>
      ) : (
        <div className="divide-y divide-slate-200">
          {items.map((item) => (
            <ItemRow key={item.id} item={item} onDelete={onRemove} />
          ))}
        </div>
      )}
    </section>
  );
}