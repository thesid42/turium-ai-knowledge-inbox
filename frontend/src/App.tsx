/**
 * Main App component with the 2-column layout.
 * Single owner of useItems and useQuery hooks.
 */

import { useEffect } from 'react';
import { Header } from './components/Header';
import { IngestForm } from './components/IngestForm';
import { ItemList } from './components/ItemList';
import { QueryPanel } from './components/QueryPanel';
import { AnswerCard } from './components/AnswerCard';
import { useItems } from './hooks/useItems';
import { useQuery } from './hooks/useQuery';

function App() {
  const { refresh: refreshItems, ingest, remove, items, total, loading, error } = useItems();
  const query = useQuery();

  // Initial load of items
  useEffect(() => {
    void refreshItems();
  }, [refreshItems]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="container py-6">
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Left column: Ingest + Items */}
          <div className="space-y-6 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:sticky lg:top-24">
            <IngestForm onIngest={ingest} />
            <ItemList
              items={items}
              total={total}
              loading={loading}
              error={error}
              onRefresh={refreshItems}
              onRemove={remove}
            />
          </div>

          {/* Right column: Query + Answer */}
          <div className="space-y-6 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:sticky lg:top-24">
            <QueryPanel ask={query.ask} loading={query.loading} reset={query.reset} />
            <AnswerCard
              answer={query.answer}
              citations={query.citations}
              provider={query.provider}
              model={query.model}
              warnings={query.warnings}
              loading={query.loading}
              error={query.error}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;