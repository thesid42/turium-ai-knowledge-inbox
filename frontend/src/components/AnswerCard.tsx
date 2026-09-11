/**
 * AnswerCard component for displaying the RAG answer with citations.
 */

import type { Citation } from '../types';
import { WarningBanner, EmptyState } from './ui';
import ReactMarkdown from 'react-markdown';
import type { HTMLAttributes, AnchorHTMLAttributes } from 'react';

interface AnswerCardProps {
  answer: string | null;
  citations: Citation[];
  provider: string | null;
  model: string | null;
  warnings: string[];
  loading: boolean;
  error: Error | null;
}

function getHostnameSafe(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

const formatScore = (score: number): string => {
  return score.toFixed(2);
};

const getProviderLabel = (provider: string | null): string => {
  if (!provider) return 'Unknown';
  return provider === 'offline' ? 'Offline (lexical)' : provider;
};

const Paragraph = ({ children }: HTMLAttributes<HTMLParagraphElement>) => (
  <p className="mb-3 last:mb-0 leading-relaxed text-slate-700">{children}</p>
);

const Strong = ({ children }: HTMLAttributes<HTMLElement>) => (
  <strong className="font-semibold text-slate-900">{children}</strong>
);

const UnorderedList = ({ children }: HTMLAttributes<HTMLUListElement>) => (
  <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>
);

const OrderedList = ({ children }: HTMLAttributes<HTMLOListElement>) => (
  <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>
);

const ListItem = ({ children }: HTMLAttributes<HTMLLIElement>) => (
  <li className="pl-0.5">{children}</li>
);

const Heading1 = ({ children }: HTMLAttributes<HTMLHeadingElement>) => (
  <h1 className="font-semibold text-slate-900 mt-4 mb-2 text-3xl">{children}</h1>
);

const Heading2 = ({ children }: HTMLAttributes<HTMLHeadingElement>) => (
  <h2 className="font-semibold text-slate-900 mt-4 mb-2 text-2xl">{children}</h2>
);

const Heading3 = ({ children }: HTMLAttributes<HTMLHeadingElement>) => (
  <h3 className="font-semibold text-slate-900 mt-4 mb-2 text-xl">{children}</h3>
);

const InlineCode = ({ children, className }: HTMLAttributes<HTMLElement>) =>
  className && typeof className === 'string' && className.startsWith('language-') ? (
    <code className={className}>{children}</code>
  ) : (
    <code className="bg-slate-100 text-indigo-700 px-1.5 py-0.5 rounded text-sm font-mono">
      {children}
    </code>
  );

const Pre = ({ children }: HTMLAttributes<HTMLPreElement>) => (
  <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto mb-3 text-sm">
    {children}
  </pre>
);

const Link = ({ children, href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
  <a
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    className="text-indigo-600 hover:underline"
    {...props}
  >
    {children}
  </a>
);

const Blockquote = ({ children }: HTMLAttributes<HTMLQuoteElement>) => (
  <blockquote className="border-l-4 border-slate-200 pl-3 text-slate-600 mb-3">{children}</blockquote>
);

const markdownComponents = {
  p: Paragraph,
  strong: Strong,
  ul: UnorderedList,
  ol: OrderedList,
  li: ListItem,
  h1: Heading1,
  h2: Heading2,
  h3: Heading3,
  code: InlineCode,
  pre: Pre,
  a: Link,
  blockquote: Blockquote,
};

export function AnswerCard({ answer, citations, provider, model, warnings, loading, error }: AnswerCardProps) {
  if (loading && !answer) {
    return (
      <section className="card" aria-busy="true" aria-label="Generating answer">
        <div className="p-8 flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-3 border-slate-200 border-t-indigo-600 rounded-full animate-spin" aria-hidden="true"></div>
          <p className="text-slate-500">Searching your knowledge base…</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="card" aria-live="polite">
        <div className="p-6">
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm" role="alert">
            {error.message}
          </div>
        </div>
      </section>
    );
  }

  if (!answer) {
    return (
      <section className="card" aria-labelledby="answer-heading">
        <div className="p-8">
          <EmptyState
            icon={
              <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.5-2.914 3.357" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9 9 4.03 9 9z" />
              </svg>
            }
            title="Ask a question"
            description="Type a question in the panel to search your saved content."
          />
        </div>
      </section>
    );
  }

  return (
    <section className="card" aria-labelledby="answer-heading">
      <div className="p-5">
        <h2 id="answer-heading" className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
          Answer
          {loading && (
            <span className="w-4 h-4 border-2 border-slate-200 border-t-indigo-600 rounded-full animate-spin" aria-hidden="true" aria-label="Loading"></span>
          )}
        </h2>

        <div className="mb-5">
          <ReactMarkdown components={markdownComponents}>{answer}</ReactMarkdown>
        </div>

        {warnings.length > 0 && (
          <div className="mb-5 space-y-2">
            {warnings.map((warning, i) => (
              <WarningBanner key={i} message={warning} />
            ))}
          </div>
        )}

        {citations.length > 0 && (
          <div className="border-t border-slate-200 pt-5">
            <h3 className="text-sm font-medium text-slate-700 mb-3">Sources ({citations.length})</h3>
            <div className="space-y-3">
              {citations.map((citation) => (
                <article
                  key={citation.chunk_id}
                  className="bg-slate-50 rounded-lg border border-slate-200 p-4"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center">
                      {citation.index}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        {citation.title && (
                          <span className="font-medium text-slate-900 truncate">{citation.title}</span>
                        )}
                        {citation.source && (
                          <a
                            href={citation.source}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-indigo-600 hover:underline truncate flex-1"
                            title={citation.source}
                          >
                            {getHostnameSafe(citation.source)}
                          </a>
                        )}
                        <span className="text-xs text-slate-500 font-mono whitespace-nowrap">
                          score: {formatScore(citation.score)}
                        </span>
                      </div>
                      <div className="ml-6">
                        <pre className="text-xs text-slate-600 font-mono whitespace-pre-wrap break-words bg-white p-2 rounded border border-slate-200 max-h-32 overflow-y-auto">
                          {citation.snippet}
                        </pre>
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        )}

        <div className="mt-5 pt-4 border-t border-slate-200 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            Provider: <span className="font-medium text-slate-700">{getProviderLabel(provider)}</span>
          </span>
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            Model: <span className="font-medium text-slate-700">{model || 'unknown'}</span>
          </span>
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {citations.length} cited chunk{citations.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </section>
  );
}