/**
 * Header component with title and provider badge.
 */

import { useHealth } from '../hooks/useHealth';

export function Header() {
  const { data, loading } = useHealth();

  const getProviderLabel = (provider: string): string => {
    switch (provider) {
      case 'openai':
        return 'OpenAI';
      case 'offline':
        return 'Offline (lexical)';
      default:
        return provider;
    }
  };

  const getProviderTooltip = (provider: string, chatModel: string, embeddingModel: string): string => {
    if (provider === 'offline') {
      return 'Offline mode: uses deterministic hashed embeddings and extractive keyword-based answers. No API key required. Set OPENAI_API_KEY for semantic search and generative answers.';
    }
    return `Provider: ${provider}\nChat model: ${chatModel}\nEmbedding model: ${embeddingModel}`;
  };

  return (
    <header className="border-b border-slate-200 bg-white sticky top-0 z-10">
      <div className="container px-4 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center">
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-slate-900">Turium</h1>
        </div>
        <div className="flex items-center gap-2">
          {loading ? (
            <span className="flex items-center gap-1.5 text-sm text-slate-500" aria-busy="true">
              <span className="w-3 h-3 border-2 border-slate-200 border-t-indigo-600 rounded-full animate-spin" aria-hidden="true"></span>
              <span>Loading provider...</span>
            </span>
          ) : data ? (
            <button
              type="button"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-700 hover:bg-slate-100 transition-colors"
              title={getProviderTooltip(data.provider, data.chat_model, data.embedding_model)}
              aria-label={`Provider: ${getProviderLabel(data.provider)}`}
            >
              <span className="w-2 h-2 rounded-full bg-indigo-500" aria-hidden="true"></span>
              <span className="font-medium">{getProviderLabel(data.provider)}</span>
              <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </button>
          ) : (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span>Provider unavailable</span>
            </span>
          )}
        </div>
      </div>
    </header>
  );
}